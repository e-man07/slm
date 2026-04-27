"""Agent loop orchestrator for Sealevel CLI.

Uses a capable external model for tool-calling decisions (native OpenAI tool_calls API).
Sealevel's own model handles non-agent chat (review, gen, explain, plain chat).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from sealevel_cli.display import (
    console,
    print_assistant_label,
    print_error,
    print_info,
    print_markdown,
    print_response_separator,
    print_repl_timing,
    print_warning,
)
from sealevel_cli.permissions import PermissionPolicy, check_permission
from sealevel_cli.tools import TOOL_DEFINITIONS, ToolResult, execute as execute_tool
from sealevel_cli.session import Session as _Session  # type hint only

if TYPE_CHECKING:
    from sealevel_cli.session import Session


# ── Agent LLM config ──

AGENT_LLM_URL = os.environ.get("SEALEVEL_AGENT_URL", "https://www.sealevel.tech/api/agent")
AGENT_LLM_KEY = os.environ.get("SEALEVEL_AGENT_KEY", "")
AGENT_LLM_MODEL = os.environ.get("SEALEVEL_AGENT_MODEL", "sealevel-agent")

# System prompt for the agent model — Solana expertise + tool instructions
AGENT_SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant with filesystem tools. "
    "Use modern Anchor 0.30+ patterns (solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "Use tools to read, edit, create files and run commands. "
    "Always read a file before editing it. Keep edits small — change one function at a time."
)

# Convert tool definitions to OpenAI tools format
AGENT_TOOLS = []
for _td in TOOL_DEFINITIONS:
    AGENT_TOOLS.append({
        "type": "function",
        "function": {
            "name": _td["name"],
            "description": _td["description"],
            "parameters": _td["parameters"],
        },
    })

# Keep for backward compat (tests import this)
AGENT_TOOL_PROMPT = AGENT_SYSTEM_PROMPT


def prompt_permission(tool_name: str, args: dict) -> str:
    """Prompt user for permission to execute a tool. Returns 'y', 'n', or 'a'."""
    from rich.text import Text

    if tool_name in ("write_file", "edit_file"):
        desc = f"{tool_name}: {args.get('path', '?')}"
    elif tool_name == "run_command":
        desc = f"run: {args.get('command', '?')}"
    else:
        desc = tool_name

    msg = Text()
    msg.append("▸ ", style="accent")
    msg.append(f"Allow {desc}? ", style="muted")
    msg.append("[y/N/a] ", style="accent.dim")
    console.print(msg, end="")

    try:
        response = input().strip().lower()
        return response if response in ("y", "n", "a") else "n"
    except (KeyboardInterrupt, EOFError):
        console.print()
        return "n"


def _print_tool_call(tc_name: str, tc_args: dict, needs_approval: bool) -> None:
    """Display a tool call panel with meaningful preview."""
    from rich.panel import Panel
    from rich.text import Text

    lines = []
    if tc_name == "edit_file":
        lines.append(f"  file: {tc_args.get('path', '?')}")
        old = tc_args.get("old_text", "")
        new = tc_args.get("new_text", "")
        for line in old.splitlines()[:5]:
            lines.append(f"  [red]- {line.strip()[:70]}[/red]")
        for line in new.splitlines()[:5]:
            lines.append(f"  [green]+ {line.strip()[:70]}[/green]")
        if old.count("\n") > 5 or new.count("\n") > 5:
            lines.append("  ...")
    elif tc_name == "write_file":
        lines.append(f"  file: {tc_args.get('path', '?')}")
        content = tc_args.get("content", "")
        line_count = content.count("\n") + 1
        lines.append(f"  {line_count} lines")
    elif tc_name == "run_command":
        lines.append(f"  $ {tc_args.get('command', '?')}")
    else:
        lines.append(f"  {tc_args.get('path', tc_args.get('pattern', ''))}")

    content = "\n".join(lines) if lines else "  (no arguments)"
    suffix = " (approval needed)" if needs_approval else ""
    title = Text(f" {tc_name}{suffix} ", style="label")

    panel = Panel(content, title=title, border_style="border", padding=(0, 1), width=min(console.width, 70))
    console.print(panel)


def _print_tool_result(tc_name: str, result: ToolResult) -> None:
    """Display tool execution result."""
    from rich.text import Text
    msg = Text()
    if result.success:
        msg.append("✓ ", style="ok")
        msg.append(tc_name.upper(), style="label")
        summary = result.output.split("\n")[0][:60]
        msg.append(f"  {summary}", style="muted")
    else:
        msg.append("✗ ", style="err")
        msg.append(tc_name.upper(), style="label")
        msg.append(f"  {result.output[:60]}", style="muted")
    console.print(msg)


def _call_agent_llm(messages: list[dict], tools: list[dict], api_key: str | None = None) -> dict:
    """Call the agent LLM with native tool calling. Returns the response dict."""
    key = AGENT_LLM_KEY or api_key or ""
    resp = httpx.post(
        AGENT_LLM_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": AGENT_LLM_MODEL,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 4096,
            "temperature": 0.0,
        },
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Agent LLM error: HTTP {resp.status_code} — {resp.text[:200]}")
    return resp.json()


class AgentLoop:
    """Orchestrates the LLM ↔ tool execution loop using native tool calling."""

    MAX_ITERATIONS = 15

    def __init__(self, cwd: Path | None = None, policy: PermissionPolicy | None = None) -> None:
        self.cwd = cwd or Path.cwd()
        self.policy = policy or PermissionPolicy()

    def _get_project_tree(self, max_files: int = 50) -> str:
        """Get a compact directory listing of the project."""
        files = []
        for p in sorted(self.cwd.rglob("*")):
            if p.is_file():
                parts = p.relative_to(self.cwd).parts
                if any(part.startswith(".") or part in ("node_modules", "target", "__pycache__", ".git") for part in parts):
                    continue
                files.append(str(p.relative_to(self.cwd)))
                if len(files) >= max_files:
                    break
        return "\n".join(files) if files else "(empty project)"

    def run(self, user_message: str, session: "Session") -> None:
        """Run the agent loop until completion or max iterations."""
        from sealevel_cli.display import create_spinner

        # Build messages for the agent LLM
        tree = self._get_project_tree()
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT + f"\n\nProject files:\n{tree}"},
            {"role": "user", "content": user_message},
        ]

        final_response = ""
        t0 = time.monotonic()

        console.print()
        print_assistant_label()

        try:
            for iteration in range(self.MAX_ITERATIONS):
                if iteration == self.MAX_ITERATIONS - 2:
                    print_warning(f"Agent approaching iteration limit ({self.MAX_ITERATIONS})")

                # Call agent LLM
                spinner = create_spinner("Thinking...")
                try:
                    spinner.start()
                    response = _call_agent_llm(messages, AGENT_TOOLS, api_key=session.client.api_key)
                    spinner.stop()
                except Exception as e:
                    spinner.stop()
                    print_error(str(e))
                    return

                choice = response.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Display any text content
                content = message.get("content", "") or ""
                if content.strip():
                    print_markdown(content)

                # Check for tool calls
                tool_calls_raw = message.get("tool_calls", [])

                if not tool_calls_raw or finish_reason != "tool_calls":
                    # No tool calls — final response
                    final_response = content
                    break

                # Append assistant message (with tool_calls) to history
                messages.append(message)

                # Execute each tool call
                for tc_raw in tool_calls_raw:
                    fn = tc_raw.get("function", {})
                    tc_name = fn.get("name", "")
                    tc_id = tc_raw.get("id", "")
                    try:
                        tc_args = json.loads(fn.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tc_args = {}

                    perm = check_permission(tc_name, tc_args, self.policy)

                    # Pre-validate edit_file
                    if tc_name == "edit_file":
                        edit_path = self.cwd / tc_args.get("path", "")
                        old_text = tc_args.get("old_text", "")
                        if edit_path.is_file() and old_text:
                            try:
                                file_content = edit_path.read_text(encoding="utf-8")
                                if old_text not in file_content:
                                    result = ToolResult(False, "old_text not found in file")
                                    _print_tool_call(tc_name, tc_args, False)
                                    _print_tool_result(tc_name, result)
                                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": result.output})
                                    continue
                            except (OSError, UnicodeDecodeError):
                                pass

                    _print_tool_call(tc_name, tc_args, needs_approval=(perm is None))

                    if perm is False:
                        result = ToolResult(False, "Permission denied: sensitive file or dangerous command")
                        _print_tool_result(tc_name, result)
                        messages.append({"role": "tool", "tool_call_id": tc_id, "content": result.output})
                        continue

                    if perm is None:
                        answer = prompt_permission(tc_name, tc_args)
                        if answer == "n":
                            result = ToolResult(False, "Permission denied by user")
                            _print_tool_result(tc_name, result)
                            messages.append({"role": "tool", "tool_call_id": tc_id, "content": result.output})
                            continue
                        if answer == "a":
                            from sealevel_cli.permissions import PERMISSION_MAP
                            level = PERMISSION_MAP.get(tc_name, "execute")
                            if level == "write":
                                self.policy.auto_writes = True
                            elif level == "execute":
                                self.policy.auto_commands = True

                    # Save file checkpoint before write/edit
                    if tc_name in ("write_file", "edit_file") and "path" in tc_args:
                        path_str = tc_args["path"]
                        session._save_file_checkpoint(
                            str(self.cwd / path_str) if not os.path.isabs(path_str) else path_str
                        )

                    # Execute
                    try:
                        result = execute_tool(tc_name, tc_args, cwd=self.cwd)
                    except Exception as e:
                        result = ToolResult(False, f"Tool execution error: {e}")

                    _print_tool_result(tc_name, result)

                    # Send result back as tool message (OpenAI format)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "content": result.output,
                    })
            else:
                print_warning("Agent reached iteration limit.")
                final_response = content or "Agent stopped at iteration limit."

        except KeyboardInterrupt:
            console.print("\n[muted](agent cancelled)[/muted]")
            if final_response:
                session.history.append({"role": "user", "content": user_message})
                session.history.append({"role": "assistant", "content": final_response or "(cancelled)"})
                session.turns += 1
            return
        except Exception as e:
            print_error(f"Agent error: {e}")
            return

        # Persist to session history
        elapsed = time.monotonic() - t0
        session.history.append({"role": "user", "content": user_message})
        session.history.append({"role": "assistant", "content": final_response})
        session.turns += 1
        tokens = session._capture_tokens()
        print_repl_timing(elapsed, tokens)
        print_response_separator()
