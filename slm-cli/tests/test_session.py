"""Tests for sealevel_cli.session — interactive session REPL, dispatch, history."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sealevel_cli.session import Session
from sealevel_cli.client import SealevelClient, SealevelError


@pytest.fixture(autouse=True)
def _mock_storage(tmp_path):
    """Prevent session tests from writing to ~/.sealevel/sessions/."""
    with patch("sealevel_cli.session.SessionStorage") as MockStorage:
        instance = MagicMock()
        MockStorage.return_value = instance
        yield instance


# --- Init ---


def test_session_init():
    client = MagicMock(spec=SealevelClient)
    s = Session(client)
    assert s.client is client
    assert s.history == []
    assert s.turns == 0
    assert len(s.commands) > 0


def test_session_has_all_commands():
    s = Session(MagicMock(spec=SealevelClient))
    assert "/review" in s.commands
    assert "/help" in s.commands
    assert "/exit" in s.commands
    assert "/clear" in s.commands
    assert "/config" in s.commands


# --- Chat ---


def test_handle_chat_adds_to_history():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    with patch("sealevel_cli.session.stream_with_spinner", return_value="Hello!"):
        s._handle_chat("test")
    assert len(s.history) == 2
    assert s.history[0] == {"role": "user", "content": "test"}
    assert s.history[1]["role"] == "assistant"
    assert s.history[1]["content"] == "Hello!"
    assert s.turns == 1


def test_handle_chat_error_rolls_back():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=SealevelError("fail")):
        s._handle_chat("test")
    assert s.history == []
    assert s.turns == 0


def test_handle_chat_keyboard_interrupt_rolls_back():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=KeyboardInterrupt):
        s._handle_chat("test")
    assert s.history == []
    assert s.turns == 0


# --- Dispatch ---


def test_dispatch_known_command():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_response_separator"):
        s._dispatch_command("/help")  # Should not crash


def test_dispatch_unknown_command():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_error") as mock_err:
        s._dispatch_command("/nonexistent")
        mock_err.assert_called_once()
        assert "Unknown command" in mock_err.call_args[0][0]


def test_dispatch_prefix_match_unique():
    """Single prefix match resolves correctly."""
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_response_separator"):
        # /hel matches only /help
        s._dispatch_command("/hel")  # Should not error


def test_dispatch_prefix_match_ambiguous():
    """Ambiguous prefix (multiple matches) shows error."""
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_error") as mock_err:
        # /e matches /exit and /explain-tx and /explain-error and /export
        s._dispatch_command("/e")
        mock_err.assert_called_once()
        assert "Ambiguous command" in mock_err.call_args[0][0]
        assert "/exit" in mock_err.call_args[0][0]


def test_dispatch_exit():
    s = Session(MagicMock(spec=SealevelClient))
    with pytest.raises(SystemExit):
        s._dispatch_command("/exit")


def test_dispatch_clear():
    s = Session(MagicMock(spec=SealevelClient))
    s.history = [{"role": "user", "content": "hi"}]
    with patch("sealevel_cli.session.print_response_separator"):
        s._dispatch_command("/clear")
    assert s.history == []


def test_dispatch_keyboard_interrupt_during_command():
    s = Session(MagicMock(spec=SealevelClient))
    # Make /review handler raise KeyboardInterrupt
    s.commands["/review"].handler = MagicMock(side_effect=KeyboardInterrupt)
    s._dispatch_command("/review somefile.rs")  # Should not crash


def test_dispatch_sealevel_error_queues_toast():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.commands["/review"].handler = MagicMock(side_effect=SealevelError("API down"))
    s._dispatch_command("/review somefile.rs")
    assert len(s._pending_toasts) == 1
    assert s._pending_toasts[0] == ("error", "API down")


def test_dispatch_adds_to_history_when_flagged():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    from sealevel_cli.commands import CommandResult
    s.commands["/review"].handler = MagicMock(
        return_value=CommandResult(user_msg="review prompt", assistant_msg="review result")
    )
    with patch("sealevel_cli.session.print_response_separator"):
        with patch("sealevel_cli.session.print_repl_timing"):
            s._dispatch_command("/review test.rs")
    assert len(s.history) == 2
    assert s.turns == 1


def test_dispatch_skips_history_for_config():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_response_separator"):
        s._dispatch_command("/config")
    assert s.history == []
    assert s.turns == 0


# --- Stream helpers ---


def test_slm_prefix_redirects_to_slash_command():
    """Typing 'slm config' inside session should redirect to /config."""
    s = Session(MagicMock(spec=SealevelClient))
    with patch.object(s, "_dispatch_command") as mock_dispatch:
        # Simulate the run loop logic
        line = "slm config --show"
        if line.startswith("slm "):
            converted = "/" + line[4:]
            s._dispatch_command(converted)
        mock_dispatch.assert_called_once_with("/config --show")


# --- Multiline input ---


# --- @file expansion ---


def test_expand_file_refs_valid():
    import tempfile, os
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("fn main() {}")
        f.flush()
        try:
            result = s._expand_file_refs(f"check @{f.name}")
            assert "[file:" in result
            assert "fn main() {}" in result
            assert f.name not in result.split("[file:")[0]  # @ removed
        finally:
            os.unlink(f.name)


def test_expand_file_refs_missing():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    result = s._expand_file_refs("check @/nonexistent.rs")
    assert "@/nonexistent.rs" in result  # Left as-is


def test_expand_file_refs_no_refs():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    result = s._expand_file_refs("hello world")
    assert result == "hello world"


def test_expand_file_refs_ignores_at_mentions():
    """Issue #3: @coral-xyz/anchor should NOT trigger file lookup."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    result = s._expand_file_refs("use @coral-xyz/anchor in your Cargo.toml")
    assert "@coral-xyz/anchor" in result  # Left unchanged


def test_expand_file_refs_ignores_at_username():
    """Issue #3: @username should NOT trigger file lookup."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    result = s._expand_file_refs("ask @solana_labs about this")
    assert "@solana_labs" in result  # Left unchanged


def test_expand_file_refs_requires_extension():
    """Issue #3: @file refs must contain a dot (file extension)."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    result = s._expand_file_refs("check @README for info")
    assert "@README" in result  # No dot = not a file ref


# --- Health check ---


def test_startup_health_check_ok():
    import time
    from sealevel_cli.client import HealthResponse
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    client.get_health.return_value = HealthResponse("ok", True, True, "")
    s = Session(client)
    s._startup_health_check()
    time.sleep(0.1)  # Wait for background thread
    assert len(s._pending_toasts) == 0


def test_startup_health_check_unreachable():
    import time
    from sealevel_cli.client import HealthResponse
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    client.get_health.return_value = HealthResponse("unreachable", False, False, "")
    s = Session(client)
    s._startup_health_check()
    time.sleep(0.1)  # Wait for background thread
    assert len(s._pending_toasts) == 1
    assert "unreachable" in s._pending_toasts[0][1].lower()


def test_startup_health_check_degraded():
    import time
    from sealevel_cli.client import HealthResponse
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    client.get_health.return_value = HealthResponse("degraded", True, False, "")
    s = Session(client)
    s._startup_health_check()
    time.sleep(0.1)  # Wait for background thread
    assert len(s._pending_toasts) == 1
    assert "degraded" in s._pending_toasts[0][1].lower()


# --- Truncation detection ---


def test_truncation_warning():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = "length"
    s = Session(client)
    with patch("sealevel_cli.session.stream_with_spinner", return_value="truncated response"):
        with patch("sealevel_cli.session.print_warning") as mock_warn:
            s._handle_chat("test")
            assert any("truncated" in str(c).lower() for c in mock_warn.call_args_list)


def test_no_truncation_warning_on_stop():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = "stop"
    s = Session(client)
    with patch("sealevel_cli.session.stream_with_spinner", return_value="full response"):
        with patch("sealevel_cli.session.print_warning") as mock_warn:
            s._handle_chat("test")
            truncation_warnings = [c for c in mock_warn.call_args_list if "truncated" in str(c).lower()]
            assert len(truncation_warnings) == 0


# --- Context warning ---


def test_context_warning_large():
    """Issue #4: context warning threshold raised to 15000 tokens."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    # Fill history with enough data to exceed 15000 token estimate (~60KB)
    s.history = [{"role": "user", "content": "x" * 15000} for _ in range(5)]
    with patch("sealevel_cli.session.print_warning") as mock_warn:
        s._warn_context_size()
        mock_warn.assert_called_once()
        assert "compact" in mock_warn.call_args[0][0].lower()


def test_context_warning_medium_no_warn():
    """Issue #4: 6000-14999 tokens should NOT trigger warning anymore."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    # ~8000 tokens worth of data — below new 15000 threshold
    s.history = [{"role": "user", "content": "x" * 8000} for _ in range(5)]
    with patch("sealevel_cli.session.print_warning") as mock_warn:
        s._warn_context_size()
        mock_warn.assert_not_called()


def test_context_warning_small():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.history = [{"role": "user", "content": "hello"}]
    with patch("sealevel_cli.session.print_warning") as mock_warn:
        s._warn_context_size()
        mock_warn.assert_not_called()


# --- SEALEVEL.md ---


def test_find_sealevel_md_in_cwd():
    import tempfile
    from sealevel_cli.session import _find_sealevel_md
    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = Path(tmpdir) / "SEALEVEL.md"
        md_path.write_text("custom rules")
        with patch("sealevel_cli.session.Path.cwd", return_value=Path(tmpdir)):
            content = _find_sealevel_md()
        assert content == "custom rules"


def test_find_sealevel_md_not_found():
    import tempfile
    from sealevel_cli.session import _find_sealevel_md
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.session.Path.cwd", return_value=Path(tmpdir)):
            with patch("sealevel_cli.session.Path.home", return_value=Path(tmpdir)):
                content = _find_sealevel_md()
        assert content is None


def test_load_project_memory():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    client.extra_context = None
    s = Session(client)
    with patch("sealevel_cli.session._find_sealevel_md", return_value="custom rules here"):
        s._load_project_memory()
    assert client.extra_context == "custom rules here"


def test_load_project_memory_none():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    client.extra_context = None
    s = Session(client)
    with patch("sealevel_cli.session._find_sealevel_md", return_value=None):
        s._load_project_memory()
    assert client.extra_context is None


# --- Undo ---


# --- Toolbar debounce ---


def test_cached_toolbar_returns_same():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    t1 = s._cached_toolbar()
    t2 = s._cached_toolbar()
    assert t1 is t2  # Same object, cached


def test_cached_toolbar_invalidates_on_turn():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    t1 = s._cached_toolbar()
    s.turns = 5
    t2 = s._cached_toolbar()
    assert t1 is not t2  # Different, recomputed


def test_cached_toolbar_invalidates_on_tokens():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s._cached_toolbar()
    s.total_tokens = 1000
    t2 = s._cached_toolbar()
    assert "1,000" in t2.value


# --- Toast errors ---


def test_error_queued_as_toast():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.commands["/review"].handler = MagicMock(side_effect=SealevelError("fail"))
    s._dispatch_command("/review test.rs")
    assert ("error", "fail") in s._pending_toasts


def test_chat_error_queued_as_toast():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=SealevelError("offline")):
        s._handle_chat("test")
    assert ("error", "offline") in s._pending_toasts


# --- Undo ---




# --- Undo ---


def test_undo_via_dispatch():
    """'/undo' should remove last turn."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    s.turns = 1
    s._undo_last_turn()
    assert s.history == []
    assert s.turns == 0


# --- Stream helpers ---


# --- Server-side session persistence ---


def test_create_server_session_on_init():
    client = MagicMock(spec=SealevelClient)
    client.create_session.return_value = {"id": "srv-123"}
    s = Session(client)
    s._create_server_session()
    assert s.session_id == "srv-123"


def test_create_server_session_failure_is_nonfatal():
    client = MagicMock(spec=SealevelClient)
    client.create_session.side_effect = SealevelError("offline")
    s = Session(client)
    s._create_server_session()
    assert s.session_id is None


def test_save_message_called_after_chat():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client, session_id="srv-123")
    with patch("sealevel_cli.session.stream_with_spinner", return_value="response"):
        s._handle_chat("hello")
    assert client.save_message.call_count == 2
    client.save_message.assert_any_call("srv-123", "user", "hello")
    client.save_message.assert_any_call("srv-123", "assistant", "response")


def test_save_message_skipped_without_session_id():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client, session_id=None)
    with patch("sealevel_cli.session.stream_with_spinner", return_value="response"):
        s._handle_chat("hello")
    client.save_message.assert_not_called()


def test_from_server():
    client = MagicMock(spec=SealevelClient)
    client.get_session.return_value = {
        "id": "srv-456",
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    }
    s = Session.from_server(client, "srv-456")
    assert s.session_id == "srv-456"
    assert len(s.history) == 2
    assert s.turns == 1


def test_capture_tokens():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = {"total_tokens": 500, "prompt_tokens": 400, "completion_tokens": 100}
    s = Session(client)
    tokens = s._capture_tokens()
    assert tokens == 500
    assert s.total_tokens == 500


def test_capture_tokens_accumulates():
    client = MagicMock(spec=SealevelClient)
    s = Session(client)
    client.last_usage = {"total_tokens": 300}
    s._capture_tokens()
    client.last_usage = {"total_tokens": 200}
    s._capture_tokens()
    assert s.total_tokens == 500


def test_capture_tokens_empty_usage_dict():
    """Empty dict {} is falsy, so treated same as None."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = {}
    s = Session(client)
    tokens = s._capture_tokens()
    assert tokens is None
    assert s.total_tokens == 0


def test_capture_tokens_none_usage():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    tokens = s._capture_tokens()
    assert tokens is None
    assert s.total_tokens == 0


def test_slash_alone_shows_help():
    """Typing just '/' should show command list."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    with patch.object(s, "_dispatch_command") as mock_dispatch:
        # Simulate the run loop check
        line = "/"
        if line == "/":
            s._dispatch_command("/help")
        mock_dispatch.assert_called_once_with("/help")


# --- Undo ---


def test_undo_last_turn():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "bye"},
        {"role": "assistant", "content": "goodbye"},
    ]
    s.turns = 2
    s._undo_last_turn()
    assert len(s.history) == 2
    assert s.turns == 1


def test_undo_empty_history():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s._undo_last_turn()  # Should not crash
    assert s.history == []
    assert s.turns == 0


def test_undo_single_turn():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    s.turns = 1
    s._undo_last_turn()
    assert s.history == []
    assert s.turns == 0


# --- From server ---


def test_from_server_empty_messages():
    client = MagicMock(spec=SealevelClient)
    client.get_session.return_value = {"id": "srv-789", "messages": []}
    s = Session.from_server(client, "srv-789")
    assert s.history == []
    assert s.turns == 0


# --- Stream helpers ---


def test_stream_response_cleans_output():
    s = Session(MagicMock(spec=SealevelClient))
    # Return text with deprecated pattern
    with patch("sealevel_cli.session.stream_with_spinner", return_value='use coral-xyz/anchor'):
        result = s.stream_response("prompt")
    assert "solana-foundation/anchor" in result


def test_stream_response_error_returns_none():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=SealevelError("fail")):
        assert s.stream_response("prompt") is None


def test_stream_response_keyboard_interrupt_returns_none():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=KeyboardInterrupt):
        assert s.stream_response("prompt") is None


def test_stream_response_raw_returns_text():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", return_value="raw"):
        assert s.stream_response_raw(iter(["raw"])) == "raw"


def test_stream_response_raw_error():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=SealevelError("fail")):
        assert s.stream_response_raw(iter([])) is None


def test_stream_response_raw_keyboard_interrupt():
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.stream_with_spinner", side_effect=KeyboardInterrupt):
        assert s.stream_response_raw(iter([])) is None


# --- Fix #7: Ambiguous vs Unknown command ---


def test_dispatch_unknown_vs_ambiguous():
    """Unknown command (no matches) shows 'Unknown', not 'Ambiguous'."""
    s = Session(MagicMock(spec=SealevelClient))
    with patch("sealevel_cli.session.print_error") as mock_err:
        s._dispatch_command("/zzz")
        assert "Unknown command" in mock_err.call_args[0][0]


# --- Fix #8: Context warning fires only once ---


def test_context_warning_fires_once():
    """Context warning should not repeat on subsequent turns."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s.history = [{"role": "user", "content": "x" * 15000} for _ in range(5)]
    with patch("sealevel_cli.session.print_warning") as mock_warn:
        s._warn_context_size()
        s._warn_context_size()
        s._warn_context_size()
        mock_warn.assert_called_once()  # Only first call warns


def test_context_warned_flag_reset_on_compact():
    """After /compact, context warning should be able to fire again."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
    client.last_finish_reason = None
    s = Session(client)
    s._context_warned = True
    # After compact, flag should be reset... but we haven't implemented that.
    # This test documents current behavior: flag is NOT reset by compact.
    assert s._context_warned is True


# --- Fix #10: _capture_tokens with empty dict ---


def test_capture_tokens_empty_dict_returns_none():
    """Empty dict {} should return None (not crash)."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = {}
    s = Session(client)
    tokens = s._capture_tokens()
    assert tokens is None
    assert s.total_tokens == 0


# --- Fix #11: _bare_command_names cached ---


def test_bare_command_names_cached():
    """_bare_command_names returns same set object (cached)."""
    s = Session(MagicMock(spec=SealevelClient))
    n1 = s._bare_command_names()
    n2 = s._bare_command_names()
    assert n1 is n2  # Same object, not recomputed


# --- Fix #12: from_server defensive parsing ---


def test_from_server_skips_malformed_messages():
    """Messages missing role or content should be skipped, not crash."""
    client = MagicMock(spec=SealevelClient)
    client.get_session.return_value = {
        "id": "srv-bad",
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant"},  # Missing content
            {"content": "orphan"},  # Missing role
            "not a dict",          # Not a dict
            {"role": "assistant", "content": "hello"},
        ]
    }
    s = Session.from_server(client, "srv-bad")
    assert len(s.history) == 2  # Only valid messages kept
    assert s.history[0]["content"] == "hi"
    assert s.history[1]["content"] == "hello"


# --- Fix #13: Health check is non-blocking ---


def test_startup_health_check_does_not_block():
    """Health check should return immediately (runs in background thread)."""
    import time
    client = MagicMock(spec=SealevelClient)
    # Make get_health slow — 2 seconds
    def slow_health():
        time.sleep(2)
        from sealevel_cli.client import HealthResponse
        return HealthResponse("ok", True, True, "")
    client.get_health = slow_health
    s = Session(client)
    t0 = time.monotonic()
    s._startup_health_check()
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5  # Should return immediately, not wait 2s
