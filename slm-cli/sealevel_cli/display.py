"""Display formatting for Sealevel CLI.

Design language: "Olive-Mono Sharp"
- Monospace-first, zero border-radius (sharp box chars)
- Chartreuse accent (#b3e62e) used sparingly as punctuation
- Uppercase labels with letter-spacing for hierarchy
- Minimal, structured, technical — Bloomberg Terminal meets GitHub CLI

Matches the Sealevel web app (sealevel.tech) design system.
"""
from __future__ import annotations

import sys
import time as _time

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.status import Status
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from sealevel_cli import __version__

# ── Sealevel color palette (dark mode — from web app globals.css oklch values) ──
#
# Mapped from .dark {} in globals.css:
#   accent/chart-1: oklch(0.897 0.196 126.665)  → #c8f542  bright chartreuse
#   chart-2:        oklch(0.768 0.233 130.85)    → #6dbf28  medium green
#   chart-3:        oklch(0.648 0.2 131.684)     → #4a9418  dim green
#   foreground:     oklch(0.988 0.003 106.5)     → #f9f8f5  warm white
#   muted-fg:       oklch(0.737 0.021 106.9)     → #b0ada4  warm gray
#   destructive:    oklch(0.704 0.191 22.216)    → #f0654a  warm red
#   t-key:          oklch(0.85 0.08 80)          → #dbb868  golden
#   t-str:          oklch(0.85 0.14 140)         → #5ec6a4  teal
#   t-comment:      oklch(0.5 0.02 107)          → #787468  olive gray

ACCENT = "#c8f542"        # chartreuse — bright, vivid (dark mode chart-1)
ACCENT_DIM = "#6dbf28"    # medium green (chart-2)
MUTED = "#b0ada4"         # warm gray — muted-foreground
BORDER = "#787468"        # olive gray — t-comment / subtle border
ERROR = "#f0654a"         # warm coral red — destructive
WARN = "#eab308"          # amber for warnings
SUCCESS = "#c8f542"       # same as accent
INFO = "#787468"          # olive gray for dim info

# ── Rich theme ──

sealevel_theme = Theme({
    "accent": Style(color=ACCENT, bold=True),
    "accent.dim": Style(color=ACCENT_DIM),
    "muted": Style(color=MUTED),
    "border": Style(color=BORDER),
    "err": Style(color=ERROR, bold=True),
    "warn": Style(color=WARN),
    "ok": Style(color=SUCCESS),
    "info": Style(color=INFO),
    "label": Style(color=MUTED, bold=True),
    "key": Style(color="#dbb868"),       # golden (t-key from web)
    "value": Style(color="#5ec6a4"),     # teal (t-str from web)
    "prompt.user": Style(color=ACCENT, bold=True),
    "prompt.arrow": Style(color=ACCENT),
})

console = Console(theme=sealevel_theme, highlight=False)


# ── Brand header ──

def print_header(subtitle: str = "") -> None:
    """Print the Sealevel brand header."""
    header = Text()
    header.append("◆ ", style="accent")
    header.append("SEALEVEL", style="bold")
    header.append(f"  v{__version__}", style="muted")
    if subtitle:
        header.append(f"  ›  {subtitle.upper()}", style="muted")
    console.print()
    console.print(header)
    console.print(Rule(style="border"))



# ── Chat formatting ──

def print_user_message(message: str) -> None:
    """Print a user message with prompt indicator."""
    prompt = Text()
    prompt.append("❯ ", style="prompt.arrow")
    prompt.append(message)
    console.print(prompt)
    console.print()


def print_assistant_label() -> None:
    """Print the assistant label before streaming response."""
    label = Text()
    label.append("◆ ", style="accent.dim")
    label.append("SEALEVEL", style="label")
    console.print(label)


def print_streaming(chunk: str) -> None:
    """Print a streaming chunk without a newline."""
    console.print(chunk, end="", highlight=False)


def print_done() -> None:
    """Print newline + separator after streaming completes."""
    console.print()


def print_response_separator() -> None:
    """Print a visual separator between responses."""
    console.print()
    console.print(Rule(style="border"))
    console.print()


# ── Structured output ──

def print_error_result(
    program: str,
    name: str,
    code: int,
    hex_code: str,
    message: str,
) -> None:
    """Print a formatted error lookup result."""
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column(style="label", width=10, no_wrap=True)
    table.add_column()
    table.add_row("PROGRAM", Text(program, style="bold"))
    table.add_row("ERROR", Text(name, style="err"))
    table.add_row("CODE", Text(f"{code} ({hex_code})", style="value"))
    table.add_row("MESSAGE", Text(message))

    panel = Panel(
        table,
        title=Text(" ERROR LOOKUP ", style="label"),
        border_style="border",
        padding=(1, 2),
    )
    console.print(panel)


def format_error_result(
    program: str,
    name: str,
    code: int,
    hex_code: str,
    message: str,
) -> str:
    """Format an error lookup result as a plain string (for testing)."""
    lines = [
        f"Program:  {program}",
        f"Error:    {name}",
        f"Code:     {code} ({hex_code})",
        f"Message:  {message}",
    ]
    return "\n".join(lines)


def print_config_table(config: dict[str, str]) -> None:
    """Print configuration as a styled table."""
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column(style="label", width=12, no_wrap=True)
    table.add_column()

    for k, v in sorted(config.items()):
        display_value = v
        if k == "api_key" and v and len(v) > 8:
            display_value = v[:8] + "···" + v[-4:]
        key_text = k.upper().replace("_", " ")
        table.add_row(key_text, Text(display_value, style="value"))

    panel = Panel(
        table,
        title=Text(" CONFIGURATION ", style="label"),
        border_style="border",
        padding=(1, 2),
    )
    console.print(panel)


def print_config_set(key: str, value: str) -> None:
    """Print a config-set confirmation."""
    display = value
    if key == "api_key" and len(value) > 8:
        display = value[:8] + "···" + value[-4:]
    msg = Text()
    msg.append("✓ ", style="ok")
    msg.append(key.upper().replace("_", " "), style="label")
    msg.append("  ", style="muted")
    msg.append(display, style="value")
    console.print(msg)


# ── Warning / error messages ──

def print_warning(message: str) -> None:
    """Print a styled warning message."""
    msg = Text()
    msg.append("▲ ", style="warn")
    msg.append(message)
    console.print(msg)


def print_error(message: str) -> None:
    """Print a styled error message."""
    msg = Text()
    msg.append("✗ ", style="err")
    msg.append(message, style="err")
    console.print(msg)


def print_success(message: str) -> None:
    """Print a styled success message."""
    msg = Text()
    msg.append("✓ ", style="ok")
    msg.append(message)
    console.print(msg)


def print_toasts(items: list[tuple[str, str]]) -> None:
    """Render queued toast messages (errors/warnings accumulated between prompts)."""
    for level, message in items:
        msg = Text()
        if level == "error":
            msg.append("✗ ", style="err")
            msg.append(message, style="err")
        elif level == "warning":
            msg.append("▲ ", style="warn")
            msg.append(message)
        else:
            msg.append("ℹ ", style="muted")
            msg.append(message, style="muted")
        console.print(msg)
    if items:
        console.print()


def print_info(message: str) -> None:
    """Print a styled info/dim message."""
    console.print(Text(message, style="muted"))


# ── Markdown rendering ──

def format_markdown(text: str) -> str:
    """Convert markdown text to plain string (for testing)."""
    result = text
    for char in ["#", "*", "_", "`"]:
        result = result.replace(char, "")
    return result.strip()


def print_markdown(text: str) -> None:
    """Render markdown to the terminal using Rich."""
    md = Markdown(text)
    console.print(md)


# ── Spinner ──

def create_spinner(message: str = "Thinking...") -> Status:
    """Create a Rich spinner with Sealevel styling."""
    return console.status(
        Text(message, style="muted"),
        spinner="dots",
        spinner_style="accent",
    )


# ── ASCII logo ──

LOGO = [
    "  ╭──────────────────╮",
    "  │    ▄▄▄▄▄▄▄▄▄▄    │",
    "  │   ▄▄▄▄▄▄▄▄▄▄▄▄   │",
    "  │    ▄▄▄▄▄▄▄▄▄▄    │",
    "  ╰──────────────────╯",
]


# ── Branded version ──

def print_version() -> None:
    """Print branded version output."""
    ver = Text()
    ver.append("◆ ", style="accent")
    ver.append("SEALEVEL", style="bold")
    ver.append(f"  v{__version__}", style="muted")
    console.print(ver)
    console.print(Text("Solana/Anchor development assistant", style="muted"))
    console.print(Text("https://sealevel.tech", style="value"))


# ── Streaming with spinner ──

def stream_with_spinner(chunks, label: bool = True, render_md: bool = True):
    """Stream chunks with progressive markdown rendering or raw output.

    Three modes:
    - render_md=True (default): Progressive live markdown — updates as chunks arrive
    - render_md=False: Raw streaming to stdout (for piping/file output)
    """
    if label:
        print_assistant_label()

    full = ""
    first = True

    if render_md:
        # Progressive markdown rendering with Live
        spinner = create_spinner("Thinking...")
        chunk_count = 0
        live = None
        try:
            spinner.start()
            for chunk in chunks:
                full += chunk
                chunk_count += 1
                if first:
                    spinner.stop()
                    first = False
                    console.print()
                    live = Live(
                        Markdown(full),
                        console=console,
                        refresh_per_second=30,
                        vertical_overflow="visible",
                    )
                    live.start()
                    _last_update = _time.monotonic()
                    _pending = 0
                else:
                    _pending += len(chunk)
                    elapsed_ms = (_time.monotonic() - _last_update) * 1000
                    if elapsed_ms >= 100 or _pending >= 50:
                        live.update(Markdown(full))
                        _last_update = _time.monotonic()
                        _pending = 0
        finally:
            if first:
                spinner.stop()
            if live:
                live.update(Markdown(full))
                live.stop()
    else:
        # Raw streaming (for file write / non-interactive)
        spinner = create_spinner("Connecting...")
        try:
            spinner.start()
            for chunk in chunks:
                if first:
                    spinner.stop()
                    first = False
                print_streaming(chunk)
                full += chunk
        finally:
            if first:
                spinner.stop()
        print_done()

    if not full.strip():
        print_warning("Empty response — model may be unavailable")

    return full


# ── Interactive REPL ──

def print_repl_header() -> None:
    """Print the REPL welcome header."""
    print_header("CHAT")
    hints = Text()
    hints.append("Interactive mode", style="muted")
    hints.append("  │  ", style="border")
    hints.append("exit", style="value")
    hints.append(" to quit", style="muted")
    hints.append("  │  ", style="border")
    hints.append("Ctrl+C", style="value")
    hints.append(" to cancel", style="muted")
    console.print(hints)
    console.print()


def print_repl_goodbye(turns: int = 0) -> None:
    """Print the REPL exit message."""
    console.print()
    msg = Text()
    msg.append("Goodbye.", style="muted")
    if turns > 0:
        msg.append(f"  ({turns} turn{'s' if turns != 1 else ''})", style="muted")
    console.print(msg)


def print_repl_timing(elapsed: float, tokens: int | None = None) -> None:
    """Print response timing and optional token count after a REPL turn."""
    if elapsed >= 1.0:
        time_str = f"{elapsed:.1f}s"
    else:
        time_str = f"{elapsed * 1000:.0f}ms"
    msg = Text()
    msg.append(f"  {time_str}", style="muted")
    if tokens:
        msg.append(f"  ·  {tokens:,} tokens", style="muted")
    console.print(msg)




# ── Session header ──

def print_session_header() -> None:
    """Print the branded session welcome with logo, like Claude Code's welcome screen."""
    console.print()
    # Logo in accent color
    for line in LOGO:
        console.print(Text(line, style="accent"))

    # Brand info next to logo area
    brand = Text()
    brand.append("  Sealevel", style="bold")
    brand.append(f"  v{__version__}", style="muted")
    console.print(brand)

    info = Text()
    info.append("  slm-8b", style="muted")
    info.append("  ·  ", style="border")
    info.append("sealevel.tech", style="value")
    console.print(info)

    console.print()
    console.print(Rule(style="border"))

    hints = Text()
    hints.append("Type to chat", style="muted")
    hints.append("  │  ", style="border")
    hints.append("/", style="value")
    hints.append(" commands", style="muted")
    hints.append("  │  ", style="border")
    hints.append("Ctrl+O", style="value")
    hints.append(" search", style="muted")
    hints.append("  │  ", style="border")
    hints.append("Esc Esc", style="value")
    hints.append(" undo", style="muted")
    console.print(hints)
    console.print()


def print_command_help(commands: dict) -> None:
    """Print a styled table of all slash commands."""
    table = Table(
        show_header=True,
        header_style="label",
        box=None,
        padding=(0, 2),
        show_edge=False,
    )
    table.add_column("COMMAND", style="accent", no_wrap=True, width=18)
    table.add_column("DESCRIPTION", style="muted")

    for cmd in commands.values():
        table.add_row(cmd.usage, cmd.help_text)

    panel = Panel(
        table,
        title=Text(" COMMANDS ", style="label"),
        border_style="border",
        padding=(1, 2),
    )
    console.print(panel)


# ── Status & Usage tables ──

def print_status_table(health, config: dict[str, str], api_key: str | None) -> None:
    """Print API status + local config in a panel."""
    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="label", width=12, no_wrap=True)
    table.add_column()

    # Services
    def svc(name: str, ok: bool) -> Text:
        t = Text()
        t.append("● " if ok else "○ ", style="ok" if ok else "err")
        t.append(name)
        return t

    table.add_row("SGLANG", svc("connected", health.sglang))
    table.add_row("RAG", svc("connected", health.rag))
    table.add_row("", Text())

    # Config
    table.add_row("API URL", Text(config.get("api_url", "—"), style="value"))
    key_display = "—"
    if api_key and len(api_key) > 8:
        key_display = api_key[:8] + "···" + api_key[-4:]
    elif api_key:
        key_display = api_key
    table.add_row("API KEY", Text(key_display, style="value"))
    table.add_row("MODE", Text(config.get("mode", "quality"), style="value"))

    # Overall status
    status_text = Text()
    if health.status == "ok":
        status_text.append("● ", style="ok")
        status_text.append("ALL SYSTEMS OPERATIONAL", style="ok")
    elif health.status == "degraded":
        status_text.append("▲ ", style="warn")
        status_text.append("DEGRADED", style="warn")
    else:
        status_text.append("○ ", style="err")
        status_text.append("UNREACHABLE", style="err")
    table.add_row("", Text())
    table.add_row("STATUS", status_text)

    panel = Panel(table, title=Text(" STATUS ", style="label"), border_style="border", padding=(1, 2))
    print_header("STATUS")
    console.print(panel)


def print_usage_table(usage) -> None:
    """Print usage statistics in a panel."""
    table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
    table.add_column(style="label", width=12, no_wrap=True)
    table.add_column()

    table.add_row("TIER", Text(usage.tier.upper(), style="accent"))
    table.add_row("", Text())
    table.add_row("TODAY", Text(f"{usage.today_requests} requests  ·  {usage.today_tokens:,} tokens", style="value"))

    # 7-day history
    if usage.daily:
        table.add_row("", Text())
        table.add_row("LAST 7 DAYS", Text())
        max_tokens = max((d.get("tokens", 0) for d in usage.daily), default=1) or 1
        for day in usage.daily:
            date = day.get("date", "?")[-5:]  # MM-DD
            tokens = day.get("tokens", 0)
            bar_len = int((tokens / max_tokens) * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            row = Text()
            row.append(f"{date}  ", style="muted")
            row.append(bar, style="accent.dim")
            row.append(f"  {tokens:,}", style="muted")
            table.add_row("", row)

    # By endpoint
    if usage.by_endpoint:
        table.add_row("", Text())
        table.add_row("ENDPOINTS", Text())
        for ep in usage.by_endpoint:
            endpoint = ep.get("endpoint", "?")
            reqs = ep.get("requests", 0)
            table.add_row("", Text(f"  {endpoint}  ·  {reqs} requests", style="muted"))

    panel = Panel(table, title=Text(" USAGE ", style="label"), border_style="border", padding=(1, 2))
    print_header("USAGE")
    console.print(panel)


# ── Sessions table ──

def print_sessions_table(sessions: list[dict]) -> None:
    """Print a list of sessions."""
    print_header("SESSIONS")
    if not sessions:
        print_info("No sessions found.")
        return

    table = Table(show_header=True, header_style="label", box=None, padding=(0, 2), show_edge=False)
    table.add_column("ID", style="value", no_wrap=True, width=10)
    table.add_column("TITLE", style="bold")
    table.add_column("UPDATED", style="muted", width=16)

    for s in sessions[:20]:  # Show last 20
        sid = s.get("id", "?")
        title = s.get("title", "Untitled")
        updated = s.get("updatedAt", s.get("updated_at", ""))[:16]
        table.add_row(sid[:8] + "…" if len(sid) > 8 else sid, title, updated)

    panel = Panel(table, border_style="border", padding=(1, 2))
    console.print(panel)


# ── File operation feedback ──

def print_file_written(path: str) -> None:
    """Print confirmation that a file was written."""
    msg = Text()
    msg.append("✓ ", style="ok")
    msg.append("WROTE  ", style="label")
    msg.append(path, style="value")
    console.print(msg)


def print_file_info(label: str, path: str) -> None:
    """Print a file operation info line."""
    msg = Text()
    msg.append("◆ ", style="accent.dim")
    msg.append(f"{label.upper()}  ", style="label")
    msg.append(path, style="muted")
    console.print(msg)
