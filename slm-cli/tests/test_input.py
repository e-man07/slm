"""Tests for sealevel_cli.input — prompt_toolkit integration, autocomplete, status bar."""
import pytest
from unittest.mock import MagicMock

from sealevel_cli.input import (
    SlashCommandCompleter,
    SealevelAutoSuggest,
    SUGGESTED_PROMPTS,
    make_bottom_toolbar,
    create_key_bindings,
    create_prompt_session,
    PROMPT_STYLE,
)
from sealevel_cli.commands import build_command_registry, SlashCommand


# --- SlashCommandCompleter ---


def test_completer_returns_completions_for_slash():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/re"

    completions = list(completer.get_completions(doc, MagicMock()))
    names = [c.text for c in completions]
    assert "/review" in names
    assert "/rename" in names
    assert "/resume" in names


def test_completer_no_completions_without_slash():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "hello"

    completions = list(completer.get_completions(doc, MagicMock()))
    assert completions == []


def test_completer_slash_alone_returns_all():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/"

    completions = list(completer.get_completions(doc, MagicMock()))
    assert len(completions) == len(cmds)


def test_completer_exact_match():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/help"

    completions = list(completer.get_completions(doc, MagicMock()))
    names = [c.text for c in completions]
    assert "/help" in names  # Exact match


def test_completer_no_match():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/zzz"

    completions = list(completer.get_completions(doc, MagicMock()))
    assert completions == []


def test_completion_has_display_meta():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/review"

    completions = list(completer.get_completions(doc, MagicMock()))
    assert len(completions) >= 1
    assert completions[0].display_meta is not None


# --- SealevelAutoSuggest ---


def test_auto_suggest_empty_input():
    suggest = SealevelAutoSuggest()
    buffer = MagicMock()
    doc = MagicMock()
    doc.text = ""

    suggestion = suggest.get_suggestion(buffer, doc)
    assert suggestion is not None
    assert suggestion.text in SUGGESTED_PROMPTS


def test_auto_suggest_cycles_through_prompts():
    suggest = SealevelAutoSuggest()
    buffer = MagicMock()
    doc = MagicMock()
    doc.text = ""

    suggestions = set()
    for _ in range(len(SUGGESTED_PROMPTS)):
        s = suggest.get_suggestion(buffer, doc)
        suggestions.add(s.text)
    assert len(suggestions) == len(SUGGESTED_PROMPTS)


def test_context_suggest_code_response():
    history = [{"role": "assistant", "content": "```rust\nfn main() {}\n```"}]
    suggest = SealevelAutoSuggest(history_ref=history)
    doc = MagicMock()
    doc.text = ""
    s = suggest.get_suggestion(MagicMock(), doc)
    assert s is not None
    assert s.text in ["Review this code", "Refactor this", "Write tests for this"]


def test_context_suggest_error_response():
    history = [{"role": "assistant", "content": "Error: ConstraintMut failed at 0x7D0"}]
    suggest = SealevelAutoSuggest(history_ref=history)
    doc = MagicMock()
    doc.text = ""
    s = suggest.get_suggestion(MagicMock(), doc)
    assert s is not None
    assert s.text in ["How do I fix this?", "What causes this error?", "Show me the fix"]


def test_context_suggest_explanation_response():
    history = [{"role": "assistant", "content": "This means the account was not initialized because..."}]
    suggest = SealevelAutoSuggest(history_ref=history)
    doc = MagicMock()
    doc.text = ""
    s = suggest.get_suggestion(MagicMock(), doc)
    assert s is not None
    assert s.text in ["Show me an example", "Can you elaborate?", "Write code for this"]


def test_context_suggest_empty_history_fallback():
    suggest = SealevelAutoSuggest(history_ref=[])
    doc = MagicMock()
    doc.text = ""
    s = suggest.get_suggestion(MagicMock(), doc)
    assert s is not None
    assert s.text in SUGGESTED_PROMPTS


def test_context_suggest_no_assistant_messages():
    history = [{"role": "user", "content": "hello"}]
    suggest = SealevelAutoSuggest(history_ref=history)
    doc = MagicMock()
    doc.text = ""
    s = suggest.get_suggestion(MagicMock(), doc)
    assert s is not None
    assert s.text in SUGGESTED_PROMPTS


def test_auto_suggest_non_empty_no_history():
    suggest = SealevelAutoSuggest()
    buffer = MagicMock()
    doc = MagicMock()
    doc.text = "hello world"

    # No history match, non-empty input → no suggestion
    suggestion = suggest.get_suggestion(buffer, doc)
    # History suggest returns None for unknown text
    assert suggestion is None


# --- Bottom toolbar ---


def test_toolbar_shows_model():
    session = MagicMock()
    session.turns = 0
    session.total_tokens = 0
    session.session_id = None

    result = make_bottom_toolbar(session)
    assert "slm-8b" in result.value


def test_toolbar_shows_turns():
    session = MagicMock()
    session.turns = 5
    session.total_tokens = 0
    session.session_id = None

    result = make_bottom_toolbar(session)
    assert "5 turns" in result.value


def test_toolbar_shows_tokens():
    session = MagicMock()
    session.turns = 1
    session.total_tokens = 1234
    session.session_id = None

    result = make_bottom_toolbar(session)
    assert "1,234 tokens" in result.value


def test_toolbar_shows_session_id():
    session = MagicMock()
    session.turns = 0
    session.total_tokens = 0
    session.session_id = "abcdef1234567890"

    result = make_bottom_toolbar(session)
    assert "session:abcdef12" in result.value


def test_toolbar_single_turn():
    session = MagicMock()
    session.turns = 1
    session.total_tokens = 0
    session.session_id = None

    result = make_bottom_toolbar(session)
    assert "1 turn" in result.value
    assert "1 turns" not in result.value


# --- Key bindings ---


def test_key_bindings_created():
    kb = create_key_bindings()
    assert kb is not None


# --- Prompt session ---


def test_create_prompt_session():
    cmds = build_command_registry()
    ps = create_prompt_session(cmds)
    assert ps is not None


def test_prompt_style_defined():
    # style_rules is a list of tuples, check names exist
    rule_names = [r[0] for r in PROMPT_STYLE.style_rules]
    assert "prompt" in rule_names
    assert "completion-menu" in rule_names
    assert "bottom-toolbar" in rule_names


# --- SUGGESTED_PROMPTS ---


# --- @file path completion ---


def test_completer_at_file_yields_files():
    import tempfile, os
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.rs")
        with open(test_file, "w") as f:
            f.write("fn main() {}")

        doc = MagicMock()
        doc.text_before_cursor = f"review @{tmpdir}/t"
        doc.text = doc.text_before_cursor

        completions = list(completer.get_completions(doc, MagicMock()))
        assert len(completions) >= 1
        assert any("test.rs" in c.display[0][1] for c in completions)


def test_completer_at_file_no_dir():
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "review @/nonexistent/path/t"
    doc.text = doc.text_before_cursor

    completions = list(completer.get_completions(doc, MagicMock()))
    assert completions == []


# --- SUGGESTED_PROMPTS ---


def test_completer_file_arg_for_review():
    """File path completion should work for /review <partial-path>."""
    import tempfile, os
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "lib.rs")
        with open(test_file, "w") as f:
            f.write("fn main() {}")

        doc = MagicMock()
        doc.text_before_cursor = f"/review {tmpdir}/l"
        doc.text = doc.text_before_cursor

        completions = list(completer.get_completions(doc, MagicMock()))
        assert len(completions) >= 1
        assert any("lib.rs" in str(c.display) for c in completions)


def test_completer_no_file_arg_for_non_file_commands():
    """Commands that don't expect files should not offer file completion."""
    cmds = build_command_registry()
    completer = SlashCommandCompleter(cmds)

    doc = MagicMock()
    doc.text_before_cursor = "/status foo"
    doc.text = doc.text_before_cursor

    completions = list(completer.get_completions(doc, MagicMock()))
    assert completions == []


def test_suggested_prompts_not_empty():
    assert len(SUGGESTED_PROMPTS) > 0
    for p in SUGGESTED_PROMPTS:
        assert isinstance(p, str)
        assert len(p) > 0
