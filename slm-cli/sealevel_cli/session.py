"""Interactive session for Sealevel CLI.

Provides a unified REPL where plain text is chat and /commands invoke tools.
Uses prompt_toolkit for live autocomplete, multiline input, and status bar.
"""
from __future__ import annotations

import json as _json
import os
import re
import shlex
import time
from pathlib import Path
from typing import Generator

from prompt_toolkit.formatted_text import HTML

from sealevel_cli.client import (
    SealevelClient,
    SealevelError,
    clean_model_response,
    fix_anchor_code,
)
from sealevel_cli.commands import (
    SlashCommand,
    build_command_registry,
)
from sealevel_cli.display import (
    console,
    print_error,
    print_info,
    print_repl_timing,
    print_warning,
    print_response_separator,
    print_session_header,
    stream_with_spinner,
)
from sealevel_cli.input import (
    create_prompt_session,
    make_bottom_toolbar,
)
from sealevel_cli.storage import SessionStorage


def _find_sealevel_md() -> str | None:
    """Walk from cwd up to root looking for SEALEVEL.md, fallback to ~/.sealevel/."""
    current = Path.cwd()
    while True:
        candidate = current / "SEALEVEL.md"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback to user-level
    user_md = Path.home() / ".sealevel" / "SEALEVEL.md"
    if user_md.is_file():
        return user_md.read_text(encoding="utf-8")
    return None


class Session:
    """Interactive Sealevel session with chat + slash commands."""

    def __init__(
        self,
        client: SealevelClient,
        session_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> None:
        self.client = client
        self.session_id = session_id
        self.history: list[dict[str, str]] = history or []
        self.commands = build_command_registry()
        self._bare_names: set[str] = {name.lstrip("/") for name in self.commands}
        self.turns = 0
        self.total_tokens = 0
        self.storage = SessionStorage()
        self._pending_toasts: list[tuple[str, str]] = []
        self._toolbar_cache = None
        self._toolbar_cache_key = None
        self._context_warned = False
        self.agent_mode = False

    def run(self) -> None:
        """Main REPL loop."""
        print_session_header()
        self._load_project_memory()
        self._create_server_session()
        self._startup_health_check()

        # Create prompt_toolkit session with live autocomplete
        prompt_session = create_prompt_session(self.commands, history_ref=self.history)

        while True:
            # Show queued toasts from previous iteration
            if self._pending_toasts:
                from sealevel_cli.display import print_toasts
                print_toasts(self._pending_toasts)
                self._pending_toasts.clear()

            try:
                raw = prompt_session.prompt(
                    HTML("<prompt>❯ </prompt>"),
                    bottom_toolbar=self._cached_toolbar,
                )
            except (KeyboardInterrupt, EOFError):
                self._goodbye()
                return

            line = raw.strip()
            if not line:
                continue

            # Plain text exit commands
            if line.lower() in ("exit", "quit", "/quit"):
                self._goodbye()
                return

            # Undo last turn (Esc+Esc sends "/undo")
            if line == "/undo":
                self._undo_last_turn()
                continue

            if line == "/retry":
                self._retry_last_turn()
                continue

            if line == "/":
                self._dispatch_command("/help")
            elif line.startswith("/"):
                self._dispatch_command(line)
            elif line.startswith("slm "):
                converted = "/" + line[4:]
                print_info(f"Tip: inside session, use {converted}")
                self._dispatch_command(converted)
            elif line in self._bare_command_names():
                print_info(f"Tip: use /{line}")
                self._dispatch_command(f"/{line}")
            elif self.agent_mode:
                self._handle_agent_chat(line)
            else:
                self._handle_chat(line)

    def _load_project_memory(self) -> None:
        """Load SEALEVEL.md project context if present."""
        content = _find_sealevel_md()
        if content:
            self.client.extra_context = content
            line_count = len(content.splitlines())
            print_info(f"◆ Loaded SEALEVEL.md ({line_count} lines)")

    def _cached_toolbar(self):
        """Return cached toolbar HTML, recompute only when state changes."""
        key = (self.turns, self.total_tokens, self.session_id, self.agent_mode)
        if self._toolbar_cache_key != key:
            self._toolbar_cache = make_bottom_toolbar(self)
            self._toolbar_cache_key = key
        return self._toolbar_cache

    def _startup_health_check(self) -> None:
        """Check API health at startup with a short timeout."""
        import threading

        def _check():
            health = self.client.get_health()
            if health.status == "unreachable":
                self._pending_toasts.append(("warning", "API unreachable — responses may fail"))
            elif health.status == "degraded":
                self._pending_toasts.append(("warning", "API degraded — some services down"))

        t = threading.Thread(target=_check, daemon=True)
        t.start()

    def _create_server_session(self) -> None:
        """Create a server-side session (best-effort, non-blocking)."""
        if self.session_id:
            return
        try:
            info = self.client.create_session()
            self.session_id = info.get("id")
        except SealevelError:
            pass
        # Create local backup
        sid = self.session_id or "local"
        try:
            self.storage.create(sid)
        except Exception:
            pass

    def _save_message(self, role: str, content: str) -> None:
        """Save a message to server + local backup (best-effort)."""
        sid = self.session_id or "local"
        try:
            self.storage.append(sid, role, content)
        except Exception:
            pass
        if not self.session_id:
            return
        try:
            self.client.save_message(self.session_id, role, content)
        except SealevelError:
            pass

    def _dispatch_command(self, line: str) -> None:
        """Parse and execute a slash command."""
        try:
            parts = shlex.split(line)
        except ValueError:
            parts = line.split()

        name = parts[0]
        args = parts[1:]

        cmd = self.commands.get(name)
        if not cmd:
            matches = [c for c in self.commands if c.startswith(name)]
            if len(matches) == 1:
                cmd = self.commands[matches[0]]
            elif matches:
                print_error(f"Ambiguous command: {name}  (matches: {', '.join(sorted(matches))})")
                return
            else:
                print_error(f"Unknown command: {name}  (type /help)")
                return

        try:
            t0 = time.monotonic()
            result = cmd.handler(args, self)
            elapsed = time.monotonic() - t0

            if cmd.adds_to_history and result:
                self.history.append({"role": "user", "content": result.user_msg})
                self.history.append({"role": "assistant", "content": result.assistant_msg})
                self._save_message("user", result.user_msg)
                self._save_message("assistant", result.assistant_msg)
                self.turns += 1
                tokens = self._capture_tokens()
                print_repl_timing(elapsed, tokens)
            print_response_separator()
        except SystemExit:
            self._goodbye()
            raise
        except SealevelError as e:
            self._pending_toasts.append(("error", str(e)))
        except KeyboardInterrupt:
            console.print("\n[muted](cancelled)[/muted]")

    def _handle_chat(self, text: str) -> None:
        """Send plain text as chat with full history."""
        # Expand @file references
        text = self._expand_file_refs(text)
        self.history.append({"role": "user", "content": text})
        console.print()

        # Pre-send context warning
        self._warn_context_size()

        try:
            t0 = time.monotonic()
            full = stream_with_spinner(
                self.client.stream_chat(text, history=self.history[:-1]),
            )
            elapsed = time.monotonic() - t0
            full = fix_anchor_code(clean_model_response(full))
            self.history.append({"role": "assistant", "content": full})
            self._save_message("user", text)
            self._save_message("assistant", full)
            self.turns += 1
            tokens = self._capture_tokens()

            # Truncation warning
            if self.client.last_finish_reason == "length":
                print_warning("Response may be truncated (hit token limit)")

            print_repl_timing(elapsed, tokens)
            print_response_separator()
        except SealevelError as e:
            self.history.pop()
            print_error(str(e))
        except KeyboardInterrupt:
            self.history.pop()
            console.print("\n[muted](cancelled)[/muted]")

    # In agent mode we override the long template-laden SYSTEM_PROMPT with this
    # short prompt that matches what v5 was trained on. The long version causes
    # the model to regurgitate the inline Anchor example instead of calling
    # tools. Client-side post-fix (clean_model_response + fix_anchor_code) still
    # handles deprecated patterns at display time, so guardrails are preserved.
    AGENT_SYSTEM_PROMPT = (
        "You are Sealevel, an expert Solana and Anchor development assistant. "
        "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
        "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
        "When uncertain, say so rather than guessing. "
        "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
        "Never reference coral-xyz/anchor or declare_id! - these are deprecated."
    )

    def _handle_agent_chat(self, text: str) -> None:
        """Send text through the agent loop (tool-augmented chat)."""
        from sealevel_cli.agent import AgentLoop, AGENT_TOOL_PROMPT

        # Expand @file references (same as plain chat)
        text = self._expand_file_refs(text)

        # Save originals so we restore exactly the prior client state
        original_extra = self.client.extra_context
        original_system = self.client.system_prompt_override

        # Use the short, training-matched system prompt + AGENT_TOOL_PROMPT.
        # Preserve any project-level SEALEVEL.md context if set.
        self.client.system_prompt_override = self.AGENT_SYSTEM_PROMPT
        agent_ctx = (original_extra + "\n\n" if original_extra else "") + AGENT_TOOL_PROMPT
        self.client.extra_context = agent_ctx

        try:
            loop = AgentLoop()
            loop.run(text, self)
            # Persist the collapsed history (added by AgentLoop.run)
            if len(self.history) >= 2:
                self._save_message("user", self.history[-2]["content"])
                self._save_message("assistant", self.history[-1]["content"])
        finally:
            # Restore original client state
            self.client.extra_context = original_extra
            self.client.system_prompt_override = original_system

    def stream_response(self, prompt: str, label: bool = True, render_md: bool = True) -> str | None:
        """Stream a chat response for a slash command."""
        try:
            full = stream_with_spinner(
                self.client.stream_chat(prompt),
                label=label,
                render_md=render_md,
            )
            return fix_anchor_code(clean_model_response(full))
        except SealevelError as e:
            print_error(str(e))
            return None
        except KeyboardInterrupt:
            console.print("\n[muted](cancelled)[/muted]")
            return None

    def stream_response_raw(self, chunks: Generator[str, None, None]) -> str | None:
        """Stream raw chunks (for explain-tx/explain-error)."""
        try:
            return stream_with_spinner(chunks)
        except SealevelError as e:
            print_error(str(e))
            return None
        except KeyboardInterrupt:
            console.print("\n[muted](cancelled)[/muted]")
            return None

    def _expand_file_refs(self, text: str) -> str:
        """Expand @file references in user input."""
        from sealevel_cli.commands import _read_file

        def replace_ref(match):
            path = match.group(1)
            content = _read_file(path)
            if content is None:
                return match.group(0)  # Leave as-is if file can't be read
            ext = os.path.splitext(path)[1].lstrip(".")
            return f"[file: {path}]\n```{ext}\n{content}\n```"

        return re.sub(r"@([\w./\-]+\.\w+)", replace_ref, text)

    def _warn_context_size(self) -> None:
        """Warn once if conversation history is getting large."""
        if self._context_warned or not self.history:
            return
        est_tokens = len(_json.dumps(self.history)) // 4
        if est_tokens > 15000:
            print_warning(f"Large context (~{est_tokens / 1000:.1f}K tokens) — consider /compact")
            self._context_warned = True

    def _capture_tokens(self) -> int | None:
        """Capture token count from last API call."""
        usage = self.client.last_usage
        if usage is not None and usage:
            tokens = usage.get("total_tokens", 0)
            self.total_tokens += tokens
            return tokens
        return None

    def _undo_last_turn(self) -> None:
        """Remove last user+assistant pair from history."""
        from sealevel_cli.display import print_success
        if (
            len(self.history) >= 2
            and self.history[-1]["role"] == "assistant"
            and self.history[-2]["role"] == "user"
        ):
            self.history.pop()  # assistant
            self.history.pop()  # user
            self.turns = max(0, self.turns - 1)
            print_success("Undid last turn.")
        else:
            print_info("Nothing to undo.")

    def _retry_last_turn(self) -> None:
        """Undo last turn and re-send the user message."""
        if (
            len(self.history) >= 2
            and self.history[-1]["role"] == "assistant"
            and self.history[-2]["role"] == "user"
        ):
            last_user_msg = self.history[-2]["content"]
            self.history.pop()  # assistant
            self.history.pop()  # user
            self.turns = max(0, self.turns - 1)
            print_info(f"Retrying: {last_user_msg[:60]}...")
            if self.agent_mode:
                self._handle_agent_chat(last_user_msg)
            else:
                self._handle_chat(last_user_msg)
        else:
            print_info("Nothing to retry.")

    @classmethod
    def from_server(cls, client: SealevelClient, session_id: str) -> "Session":
        """Load a session from the server."""
        detail = client.get_session(session_id)
        messages = detail.get("messages", [])
        history = []
        for m in messages:
            if isinstance(m, dict) and "role" in m and "content" in m:
                history.append({"role": m["role"], "content": m["content"]})
        session = cls(client, session_id=session_id, history=history)
        session.turns = len([m for m in history if m["role"] == "assistant"])
        return session

    def _bare_command_names(self) -> set[str]:
        return self._bare_names

    def _goodbye(self) -> None:
        from sealevel_cli.display import print_repl_goodbye
        print_repl_goodbye(self.turns)
