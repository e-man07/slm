"""Input handling for Sealevel CLI using prompt_toolkit.

Provides:
- Live slash command dropdown autocomplete
- Multiline input (Ctrl+J)
- History search (Ctrl+R)
- Clear screen (Ctrl+L)
- Ghost text suggestions
- Bottom status bar
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory, Suggestion, AutoSuggest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

if TYPE_CHECKING:
    from sealevel_cli.commands import SlashCommand

# ── Sealevel prompt_toolkit style (matches display.py palette) ──

PROMPT_STYLE = Style.from_dict({
    "prompt": "#c8f542 bold",
    "bottom-toolbar": "bg:#1a1a18 #b0ada4",
    "bottom-toolbar.text": "#b0ada4",
    "bottom-toolbar.key": "#c8f542",
    "completion-menu": "bg:#2a2a25 #f9f8f5",
    "completion-menu.completion": "bg:#2a2a25 #f9f8f5",
    "completion-menu.completion.current": "bg:#c8f542 #1a1a18",
    "completion-menu.meta": "bg:#2a2a25 #787468",
    "completion-menu.meta.current": "bg:#c8f542 #1a1a18",
    "auto-suggestion": "#787468",
})


# ── Slash command completer ──

class SlashCommandCompleter(Completer):
    """Live dropdown completer for slash commands."""

    def __init__(self, commands: dict[str, "SlashCommand"]) -> None:
        self.commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # @file path completion
        words = text.split()
        if words:
            last_word = words[-1]
            if last_word.startswith("@"):
                partial = last_word[1:]  # Remove @
                dir_path = os.path.dirname(partial) or "."
                prefix = os.path.basename(partial)
                try:
                    for entry in sorted(Path(dir_path).iterdir()):
                        name = str(entry.relative_to(".")) if dir_path == "." else str(entry)
                        if entry.name.startswith(prefix):
                            display_name = entry.name + ("/" if entry.is_dir() else "")
                            yield Completion(
                                f"@{name}",
                                start_position=-len(last_word),
                                display=display_name,
                            )
                except (OSError, ValueError):
                    pass
                return

        # File path completion for commands that expect files (e.g., /review src/li...)
        if words and len(words) >= 2:
            cmd_name = words[0]
            cmd = self.commands.get(cmd_name)
            if cmd and cmd.expects_file:
                partial = last_word
                dir_path = os.path.dirname(partial) or "."
                prefix = os.path.basename(partial)
                try:
                    for entry in sorted(Path(dir_path).iterdir()):
                        name = str(entry.relative_to(".")) if dir_path == "." else str(entry)
                        if entry.name.startswith(prefix):
                            display_name = entry.name + ("/" if entry.is_dir() else "")
                            yield Completion(
                                name,
                                start_position=-len(partial),
                                display=display_name,
                            )
                except (OSError, ValueError):
                    pass
                return

        # Slash command completion
        stripped = text.strip()
        if not stripped.startswith("/"):
            return

        for name, cmd in self.commands.items():
            if name.startswith(stripped):
                yield Completion(
                    name,
                    start_position=-len(stripped),
                    display=cmd.usage,
                    display_meta=cmd.help_text,
                )


# ── Ghost text suggestions ──

SUGGESTED_PROMPTS = [
    "How do I derive a PDA in Anchor?",
    "Write an SPL token transfer",
    "Explain error 0x1771",
    "/review",
    "/help",
]


CONTEXT_SUGGESTIONS = {
    "code": ["Review this code", "Refactor this", "Write tests for this"],
    "error": ["How do I fix this?", "What causes this error?", "Show me the fix"],
    "explanation": ["Show me an example", "Can you elaborate?", "Write code for this"],
}


class SealevelAutoSuggest(AutoSuggest):
    """Context-aware ghost text suggestions based on conversation history."""

    def __init__(
        self,
        history_suggest: AutoSuggestFromHistory | None = None,
        history_ref: list[dict[str, str]] | None = None,
    ):
        self._history = history_suggest or AutoSuggestFromHistory()
        self._history_ref = history_ref or []
        self._suggestion_index = 0

    def get_suggestion(self, buffer, document):
        # First try history-based suggestion
        hist_suggestion = self._history.get_suggestion(buffer, document)
        if hist_suggestion:
            return hist_suggestion

        # If empty input, suggest based on conversation context
        text = document.text.strip()
        if not text:
            context = self._infer_context()
            prompts = CONTEXT_SUGGESTIONS.get(context, SUGGESTED_PROMPTS)
            idx = self._suggestion_index % len(prompts)
            self._suggestion_index += 1
            return Suggestion(prompts[idx])

        return None

    def _infer_context(self) -> str | None:
        """Infer suggestion context from last assistant message."""
        if not self._history_ref:
            return None
        # Find last assistant message
        for msg in reversed(self._history_ref):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if "```" in content or "fn " in content or "pub " in content:
                    return "code"
                if any(w in content.lower() for w in ["error", "failed", "0x", "exception"]):
                    return "error"
                if any(w in content.lower() for w in ["because", "means that", "in other words", "essentially"]):
                    return "explanation"
                return None
        return None


# ── Status bar ──

def make_bottom_toolbar(session) -> HTML:
    """Build the bottom toolbar text for prompt_toolkit."""
    parts = []

    # Model + agent indicator
    model = '<key>slm-8b</key>'
    if getattr(session, 'agent_mode', False):
        model += ' <key>agent</key>'
    parts.append(model)

    # Turns
    if session.turns > 0:
        parts.append(f'<text>{session.turns} turn{"s" if session.turns != 1 else ""}</text>')

    # Tokens
    if session.total_tokens > 0:
        parts.append(f'<text>{session.total_tokens:,} tokens</text>')

    # Session ID
    if session.session_id:
        sid = session.session_id[:8]
        parts.append(f'<text>session:{sid}</text>')

    return HTML("  │  ".join(parts))


# ── Key bindings ──

def create_key_bindings() -> KeyBindings:
    """Create custom key bindings."""
    kb = KeyBindings()

    @kb.add("escape", "escape")
    def _undo_handler(event):
        """Esc+Esc: signal undo (handled by session)."""
        event.current_buffer.text = "/undo"
        event.current_buffer.validate_and_handle()

    @kb.add("c-o")
    def _search_handler(event):
        """Ctrl+O: open conversation search."""
        event.current_buffer.text = "/search "
        event.current_buffer.cursor_position = len("/search ")

    @kb.add("/", eager=True)
    def _slash_trigger(event):
        """Insert / and immediately open completion dropdown."""
        buf = event.current_buffer
        if not buf.text:
            buf.insert_text("/")
            buf.start_completion()
        else:
            buf.insert_text("/")

    # Note: completion stays open via complete_while_typing=True on PromptSession.
    # No need to bind every printable character — prompt_toolkit handles it natively.

    return kb


# ── Prompt session factory ──

def create_prompt_session(
    commands: dict[str, "SlashCommand"],
    history_ref: list[dict[str, str]] | None = None,
) -> PromptSession:
    """Create a configured prompt_toolkit PromptSession."""
    completer = SlashCommandCompleter(commands)
    auto_suggest = SealevelAutoSuggest(history_ref=history_ref)
    kb = create_key_bindings()

    # Persistent input history across sessions
    history_path = Path.home() / ".sealevel" / "prompt_history"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        history = FileHistory(str(history_path))
    except OSError:
        history = InMemoryHistory()

    return PromptSession(
        completer=completer,
        auto_suggest=auto_suggest,
        style=PROMPT_STYLE,
        key_bindings=kb,
        multiline=False,
        complete_while_typing=True,
        complete_in_thread=True,
        enable_history_search=True,
        history=history,
    )
