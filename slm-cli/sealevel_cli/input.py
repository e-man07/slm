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

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory, Suggestion, AutoSuggest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
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
        text = document.text_before_cursor.strip()

        # Only complete when input starts with /
        if not text.startswith("/"):
            return

        for name, cmd in self.commands.items():
            if name.startswith(text):
                yield Completion(
                    name,
                    start_position=-len(text),
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


class SealevelAutoSuggest(AutoSuggest):
    """Show ghost text suggestions based on context."""

    def __init__(self, history_suggest: AutoSuggestFromHistory | None = None):
        self._history = history_suggest or AutoSuggestFromHistory()
        self._suggestion_index = 0

    def get_suggestion(self, buffer, document):
        # First try history-based suggestion
        hist_suggestion = self._history.get_suggestion(buffer, document)
        if hist_suggestion:
            return hist_suggestion

        # If empty input, suggest a prompt
        text = document.text.strip()
        if not text:
            idx = self._suggestion_index % len(SUGGESTED_PROMPTS)
            self._suggestion_index += 1
            return Suggestion(SUGGESTED_PROMPTS[idx])

        return None


# ── Status bar ──

def make_bottom_toolbar(session) -> HTML:
    """Build the bottom toolbar text for prompt_toolkit."""
    parts = []

    # Model
    parts.append('<key>slm-8b</key>')

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

    @kb.add("/", eager=True)
    def _slash_trigger(event):
        """Insert / and immediately open completion dropdown."""
        buf = event.current_buffer
        if not buf.text:
            buf.insert_text("/")
            buf.start_completion()
        else:
            buf.insert_text("/")

    # Keep completion menu open while typing after /
    # Bind all printable characters to re-trigger completion when in slash mode
    import string
    for char in string.ascii_lowercase + string.ascii_uppercase + string.digits + "-_":
        @kb.add(char, eager=True)
        def _char_handler(event, c=char):
            buf = event.current_buffer
            buf.insert_text(c)
            if buf.text.startswith("/"):
                buf.start_completion()

    @kb.add("c-h", eager=True)  # Backspace
    def _backspace_handler(event):
        buf = event.current_buffer
        buf.delete_before_cursor()
        if buf.text.startswith("/"):
            buf.start_completion()

    return kb


# ── Prompt session factory ──

def create_prompt_session(
    commands: dict[str, "SlashCommand"],
) -> PromptSession:
    """Create a configured prompt_toolkit PromptSession."""
    completer = SlashCommandCompleter(commands)
    auto_suggest = SealevelAutoSuggest()
    kb = create_key_bindings()

    return PromptSession(
        completer=completer,
        auto_suggest=auto_suggest,
        style=PROMPT_STYLE,
        key_bindings=kb,
        multiline=False,
        complete_while_typing=True,
        complete_in_thread=True,
        enable_history_search=True,
        history=InMemoryHistory(),
    )
