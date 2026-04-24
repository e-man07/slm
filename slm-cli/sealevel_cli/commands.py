"""Slash command registry and handlers for Sealevel CLI session."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from sealevel_cli.session import Session


@dataclass
class CommandResult:
    """Result of a slash command that should be added to conversation history."""
    user_msg: str
    assistant_msg: str


@dataclass
class SlashCommand:
    """A registered slash command."""
    name: str
    handler: Callable[[list[str], "Session"], CommandResult | None]
    help_text: str
    usage: str
    adds_to_history: bool = True
    expects_file: bool = False


# ── Prompt templates ──

REVIEW_PROMPT = (
    "Review this Solana/Anchor code for security issues, deprecated patterns, "
    "and common mistakes. Be specific and actionable.\n\n```rust\n{code}\n```"
)

MIGRATE_PROMPT = (
    "Migrate this Solana/Anchor code to modern Anchor 0.30+ patterns. "
    "Update: declare_id! -> declare_program!, coral-xyz/anchor -> solana-foundation/anchor, "
    "manual space calculation -> InitSpace derive, bumps.get() -> ctx.bumps.field_name. "
    "Output ONLY the migrated code in a single ```rust block, no explanation.\n\n"
    "```rust\n{code}\n```"
)

GEN_PROMPT = (
    "Write a complete, production-ready Anchor program for: {description}. "
    "Use modern Anchor 0.30+ patterns. Include all necessary accounts, instructions, and account structs. "
    "Output ONLY the Rust code in a single ```rust block, no explanation."
)

TESTS_PROMPT = (
    "Write comprehensive TypeScript tests using @coral-xyz/anchor and mocha for this Anchor program. "
    "Cover all instructions with happy path and error cases. Output ONLY the TypeScript code.\n\n"
    "```rust\n{code}\n```"
)


# ── File helpers ──

SENSITIVE_FILES = {'.env', '.env.local', 'credentials.json', 'id_rsa', 'id_ed25519', '.netrc'}


def _read_file(path: str) -> str | None:
    """Read and validate a file. Returns content or None on error."""
    from sealevel_cli.display import print_error
    resolved = os.path.realpath(path)
    if not os.path.isfile(resolved):
        print_error(f"File not found: {path}")
        return None
    if os.path.getsize(resolved) > 1_000_000:
        print_error(f"File too large (max 1MB): {path}")
        return None
    basename = os.path.basename(resolved).lower()
    if basename in SENSITIVE_FILES:
        print_error(f"Cannot read sensitive file: {basename}")
        return None
    with open(resolved, "r", encoding="utf-8") as f:
        return f.read()


def _extract_rust_code(text: str) -> str:
    """Extract code from a fenced code block (any language), or return full text if no block found."""
    match = re.search(r"```\w*\n(.*?)```", text, re.DOTALL)
    return match.group(1) if match else text


def _write_code_to_file(text: str, path: str) -> None:
    """Extract code from response and write to file."""
    from sealevel_cli.display import print_file_written
    code = _extract_rust_code(text)
    with open(path, "w") as f:
        f.write(code)
    print_file_written(path)


# ── Command handlers ──

def cmd_review(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /review <file>")
        return None

    code = _read_file(args[0])
    if code is None:
        return None

    from sealevel_cli.display import print_file_info, console
    print_file_info("reviewing", args[0])
    console.print()

    prompt = REVIEW_PROMPT.format(code=code)
    full = session.stream_response(prompt)
    if full is None:
        return None
    return CommandResult(user_msg=prompt, assistant_msg=full)


def cmd_migrate(args: list[str], session: "Session") -> CommandResult | None:
    write_mode = "--write" in args or "-w" in args
    file_args = [a for a in args if a not in ("--write", "-w")]

    if not file_args:
        from sealevel_cli.display import print_info
        print_info("Usage: /migrate <file> [--write]")
        return None

    code = _read_file(file_args[0])
    if code is None:
        return None

    from sealevel_cli.display import print_file_info, console
    print_file_info("migrating", file_args[0])
    console.print()

    prompt = MIGRATE_PROMPT.format(code=code)
    # stream_response already applies fix_anchor_code + clean_model_response
    # When writing to file, don't render markdown (need raw text for extraction)
    full = session.stream_response(prompt, label=not write_mode, render_md=not write_mode)
    if full is None:
        return None

    if write_mode:
        _write_code_to_file(full, file_args[0])

    return CommandResult(user_msg=prompt, assistant_msg=full)


def cmd_gen(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /gen <description> [-o file]")
        return None

    output = None
    desc_parts = []
    i = 0
    while i < len(args):
        if args[i] in ("-o", "--output") and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        else:
            desc_parts.append(args[i])
            i += 1

    description = " ".join(desc_parts)
    if not description:
        from sealevel_cli.display import print_info
        print_info("Usage: /gen <description> [-o file]")
        return None

    from sealevel_cli.display import print_info, console
    print_info(description)
    console.print()

    prompt = GEN_PROMPT.format(description=description)
    # stream_response already applies fix_anchor_code + clean_model_response
    # When writing to file, don't render markdown (need raw text for extraction)
    full = session.stream_response(prompt, label=output is None, render_md=output is None)
    if full is None:
        return None

    if output:
        _write_code_to_file(full, output)

    return CommandResult(user_msg=prompt, assistant_msg=full)


def cmd_tests(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /tests <file> [-o output.ts]")
        return None

    output = None
    file_args = []
    i = 0
    while i < len(args):
        if args[i] in ("-o", "--output") and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        else:
            file_args.append(args[i])
            i += 1

    if not file_args:
        from sealevel_cli.display import print_info
        print_info("Usage: /tests <file> [-o output.ts]")
        return None

    code = _read_file(file_args[0])
    if code is None:
        return None

    from sealevel_cli.display import print_file_info, console
    print_file_info("generating tests for", file_args[0])
    console.print()

    prompt = TESTS_PROMPT.format(code=code)
    full = session.stream_response(prompt, label=output is None, render_md=output is None)
    if full is None:
        return None

    if output:
        _write_code_to_file(full, output)

    return CommandResult(user_msg=prompt, assistant_msg=full)


def cmd_explain_tx(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /explain-tx <signature>")
        return None

    from sealevel_cli.display import print_info, console
    sig = args[0]
    print_info(f"Signature: {sig[:16]}...")
    console.print()

    full = session.stream_response_raw(session.client.explain_tx(sig))
    if full is None:
        return None
    return CommandResult(
        user_msg=f"Explain this Solana transaction: {sig}",
        assistant_msg=full,
    )


def cmd_explain_error(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /explain-error <code>")
        return None

    from sealevel_cli.display import print_info, console
    error_code = args[0]
    print_info(f"Code: {error_code}")
    console.print()

    full = session.stream_response_raw(session.client.explain_error(error_code))
    if full is None:
        return None
    return CommandResult(
        user_msg=f"Explain Solana error code: {error_code}",
        assistant_msg=full,
    )


def cmd_status(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_status_table
    from sealevel_cli.config import load_config, get_value

    health = session.client.get_health()
    config_dir = os.environ.get("SEALEVEL_CONFIG_DIR")
    cfg = load_config(config_dir=config_dir)
    api_key = get_value("api_key", config_dir=config_dir)
    print_status_table(health, cfg, api_key)
    return None


def cmd_usage(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_usage_table
    try:
        usage = session.client.get_usage()
        print_usage_table(usage)
    except Exception as e:
        from sealevel_cli.display import print_error
        print_error(str(e))
    return None


def cmd_copy(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_success, print_info

    if not session.history:
        print_info("Nothing to copy — no responses yet.")
        return None

    # Find last assistant message
    text = None
    for msg in reversed(session.history):
        if msg["role"] == "assistant":
            text = msg["content"]
            break

    if not text:
        print_info("No assistant response to copy.")
        return None

    try:
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode(), check=True)
        else:
            print_info(f"Clipboard not supported on {sys.platform}")
            return None
        print_success("Copied last response to clipboard.")
    except FileNotFoundError:
        print_info("Clipboard tool not found. Install xclip (Linux) or use macOS/Windows.")
    except subprocess.SubprocessError as e:
        print_info(f"Clipboard failed: {e}")
    return None


def cmd_config(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.config import load_config, set_value, get_value
    from sealevel_cli.display import print_config_table, print_config_set, print_error, print_header, print_warning

    config_dir = os.environ.get("SEALEVEL_CONFIG_DIR")

    if not args or "--show" in args:
        print_header("CONFIG")
        cfg = load_config(config_dir=config_dir)
        api_key = get_value("api_key", config_dir=config_dir)
        if api_key:
            cfg["api_key"] = api_key
        print_config_table(cfg)
        return None

    i = 0
    while i < len(args):
        if args[i] == "--api-key" and i + 1 < len(args):
            key = args[i + 1]
            if not key.startswith("slm_") or len(key) < 16:
                print_error("Invalid API key. Must start with 'slm_' and be 16+ chars.")
                return None
            set_value("api_key", key, config_dir=config_dir)
            print_config_set("api_key", key)
            session.client.api_key = key
            i += 2
        elif args[i] == "--api-url" and i + 1 < len(args):
            url = args[i + 1].rstrip("/")
            if not url or not url.startswith(("http://", "https://")):
                print_error("Invalid URL. Must start with http:// or https://")
                return None
            set_value("api_url", url, config_dir=config_dir)
            print_config_set("api_url", url)
            session.client.base_url = url
            i += 2
        elif args[i] == "--mode" and i + 1 < len(args):
            if args[i + 1] not in ("quality", "fast"):
                print_error("Mode must be 'quality' or 'fast'")
                return None
            set_value("mode", args[i + 1], config_dir=config_dir)
            print_config_set("mode", args[i + 1])
            session.client.mode = args[i + 1]
            i += 2
        else:
            print_warning(f"Unknown flag: {args[i]}")
            i += 1
    return None


def cmd_sessions(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_sessions_table
    try:
        sessions = session.client.list_sessions()
        print_sessions_table(sessions)
    except Exception as e:
        from sealevel_cli.display import print_error
        print_error(str(e))
    return None


def cmd_resume(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /resume <session-id>")
        return None

    from sealevel_cli.display import print_success, print_error
    session_id = args[0]
    try:
        detail = session.client.get_session(session_id)
        messages = detail.get("messages", [])
        session.history = [{"role": m["role"], "content": m["content"]} for m in messages]
        session.session_id = session_id
        session.turns = len([m for m in session.history if m["role"] == "assistant"])
        print_success(f"Resumed session {session_id[:8]}... ({session.turns} turns)")
    except Exception as e:
        print_error(str(e))
    return None


def cmd_rename(args: list[str], session: "Session") -> CommandResult | None:
    if not args:
        from sealevel_cli.display import print_info
        print_info("Usage: /rename <new name>")
        return None

    if not session.session_id:
        from sealevel_cli.display import print_info
        print_info("No active server session to rename.")
        return None

    from sealevel_cli.display import print_success, print_error
    title = " ".join(args)
    try:
        session.client.rename_session(session.session_id, title)
        print_success(f"Session renamed: {title}")
    except Exception as e:
        print_error(str(e))
    return None


def cmd_rotate_key(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_success, print_error, print_config_set
    from sealevel_cli.config import set_value

    try:
        new_key = session.client.rotate_key()
        if not new_key:
            print_error("No key returned from server.")
            return None
        config_dir = os.environ.get("SEALEVEL_CONFIG_DIR")
        set_value("api_key", new_key, config_dir=config_dir)
        session.client.api_key = new_key
        print_success("API key rotated.")
        print_config_set("api_key", new_key)
    except Exception as e:
        print_error(str(e))
    return None


def cmd_compact(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_success, print_info

    if not session.history:
        print_info("History is already empty.")
        return None

    # Default: keep last 5 turns (10 messages)
    try:
        n_turns = int(args[0]) if args else 5
    except ValueError:
        n_turns = 5

    if n_turns < 1:
        n_turns = 1

    keep = n_turns * 2  # Each turn = user + assistant
    before = len(session.history)
    if len(session.history) > keep:
        session.history = session.history[-keep:]
    after = len(session.history)
    removed = before - after
    print_success(f"Compacted: kept last {n_turns} turns, removed {removed} messages.")
    return None


def cmd_export(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_success, print_info, print_file_written

    if not session.history:
        print_info("Nothing to export — no conversation yet.")
        return None

    filename = args[0] if args else f"sealevel-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"

    # Validate: only allow writing in current directory or subdirectories
    from pathlib import Path as _Path
    resolved = _Path(filename).resolve()
    if not resolved.is_relative_to(_Path.cwd()):
        from sealevel_cli.display import print_error
        print_error("Export path must be within current directory.")
        return None

    lines = [f"# Sealevel Session Export\n\n"]
    for msg in session.history:
        role = msg["role"].upper()
        content = msg["content"]
        lines.append(f"## {role}\n\n{content}\n\n---\n\n")

    try:
        with open(filename, "w") as f:
            f.write("".join(lines))
        print_file_written(filename)
    except OSError as e:
        from sealevel_cli.display import print_error
        print_error(f"Cannot write file: {e}")
    return None


def cmd_history(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_header, print_info, console
    from rich.text import Text

    print_header("CONVERSATION HISTORY")
    if not session.history:
        print_info("No conversation history yet.")
        return None

    # Show last 20 messages
    messages = session.history[-20:]
    for i, msg in enumerate(messages):
        role = msg["role"].upper()
        content = msg["content"][:80].replace("\n", " ")
        line = Text()
        if role == "USER":
            line.append(f"  ❯ ", style="accent")
        else:
            line.append(f"  ◆ ", style="accent.dim")
        line.append(content, style="muted" if role == "ASSISTANT" else "")
        if len(msg["content"]) > 80:
            line.append("…", style="muted")
        console.print(line)
    return None


def cmd_search(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_header, print_info, console
    from rich.table import Table
    from rich.text import Text

    if not args:
        print_info("Usage: /search <query>")
        return None

    query = " ".join(args).lower()

    if not session.history:
        print_info("No conversation to search.")
        return None

    matches = []
    for i, msg in enumerate(session.history):
        if query in msg["content"].lower():
            matches.append((i, msg))

    print_header("SEARCH")
    if not matches:
        print_info(f"No matches for '{query}'")
        return None

    table = Table(show_header=True, header_style="label", box=None, padding=(0, 2), show_edge=False)
    table.add_column("TURN", style="value", width=6)
    table.add_column("ROLE", style="label", width=10)
    table.add_column("PREVIEW", style="muted")

    for idx, msg in matches[:20]:
        turn = str(idx // 2 + 1)
        role = msg["role"].upper()
        content = msg["content"][:80].replace("\n", " ")
        preview = Text(content)
        preview.highlight_regex(f"(?i){re.escape(query)}", style="accent")
        if len(msg["content"]) > 80:
            preview.append("…", style="muted")
        table.add_row(turn, role, preview)

    console.print(table)
    return None


def cmd_clear(args: list[str], session: "Session") -> CommandResult | None:
    session.history.clear()
    from sealevel_cli.display import print_success
    print_success("History cleared.")
    return None


def cmd_help(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_command_help
    print_command_help(session.commands)
    return None


def cmd_login(args: list[str], session: "Session") -> CommandResult | None:
    from sealevel_cli.display import print_success, print_info
    if session.client.api_key:
        key = session.client.api_key
        print_info(f"Already logged in (key: {key[:8]}···{key[-4:]})")
        return None
    try:
        from sealevel_cli.main import _device_login_flow
        _device_login_flow()
        # Reload key into current session client
        from sealevel_cli.config import get_value
        new_key = get_value("api_key")
        if new_key:
            session.client.api_key = new_key
    except SystemExit:
        pass
    return None


def cmd_exit(args: list[str], session: "Session") -> CommandResult | None:
    raise SystemExit(0)


# ── Registry ──

def build_command_registry() -> dict[str, SlashCommand]:
    """Build and return the slash command registry."""
    commands = [
        SlashCommand("/review", cmd_review, "Review code for security issues", "/review <file>", expects_file=True),
        SlashCommand("/migrate", cmd_migrate, "Migrate to modern Anchor 0.30+", "/migrate <file> [--write]", expects_file=True),
        SlashCommand("/gen", cmd_gen, "Generate an Anchor program", '/gen <description> [-o file]'),
        SlashCommand("/tests", cmd_tests, "Generate TypeScript tests", "/tests <file> [-o out.ts]", expects_file=True),
        SlashCommand("/explain-tx", cmd_explain_tx, "Explain a transaction", "/explain-tx <signature>"),
        SlashCommand("/explain-error", cmd_explain_error, "Decode an error code", "/explain-error <code>"),
        SlashCommand("/status", cmd_status, "Show API status and config", "/status", adds_to_history=False),
        SlashCommand("/usage", cmd_usage, "Show token usage and limits", "/usage", adds_to_history=False),
        SlashCommand("/copy", cmd_copy, "Copy last response to clipboard", "/copy", adds_to_history=False),
        SlashCommand("/sessions", cmd_sessions, "List past sessions", "/sessions", adds_to_history=False),
        SlashCommand("/resume", cmd_resume, "Resume a past session", "/resume <id>", adds_to_history=False),
        SlashCommand("/rename", cmd_rename, "Rename current session", "/rename <name>", adds_to_history=False),
        SlashCommand("/rotate-key", cmd_rotate_key, "Rotate API key", "/rotate-key", adds_to_history=False),
        SlashCommand("/config", cmd_config, "View or set configuration", "/config [--show]", adds_to_history=False),
        SlashCommand("/compact", cmd_compact, "Trim history to last N turns", "/compact [N]", adds_to_history=False),
        SlashCommand("/export", cmd_export, "Export session as markdown", "/export [file]", adds_to_history=False),
        SlashCommand("/history", cmd_history, "Show input history", "/history", adds_to_history=False),
        SlashCommand("/search", cmd_search, "Search conversation history", "/search <query>", adds_to_history=False),
        SlashCommand("/clear", cmd_clear, "Clear conversation history", "/clear", adds_to_history=False),
        SlashCommand("/login", cmd_login, "Authenticate via browser", "/login", adds_to_history=False),
        SlashCommand("/help", cmd_help, "Show available commands", "/help", adds_to_history=False),
        SlashCommand("/exit", cmd_exit, "Exit the session", "/exit", adds_to_history=False),
    ]
    return {cmd.name: cmd for cmd in commands}
