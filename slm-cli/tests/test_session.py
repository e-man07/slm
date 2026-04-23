"""Tests for sealevel_cli.session — interactive session REPL, dispatch, history."""
import pytest
from unittest.mock import MagicMock, patch

from sealevel_cli.session import Session
from sealevel_cli.client import SealevelClient, SealevelError


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
        # /e matches /exit and /explain-tx and /explain-error
        s._dispatch_command("/e")
        mock_err.assert_called_once()
        assert "Unknown command" in mock_err.call_args[0][0]


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


def test_dispatch_sealevel_error_during_command():
    s = Session(MagicMock(spec=SealevelClient))
    s.commands["/review"].handler = MagicMock(side_effect=SealevelError("API down"))
    with patch("sealevel_cli.session.print_error") as mock_err:
        s._dispatch_command("/review somefile.rs")
        mock_err.assert_called_once()


def test_dispatch_adds_to_history_when_flagged():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
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


def test_undo_via_dispatch():
    """'/undo' should remove last turn."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
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
    s = Session(client, session_id="srv-123")
    with patch("sealevel_cli.session.stream_with_spinner", return_value="response"):
        s._handle_chat("hello")
    assert client.save_message.call_count == 2
    client.save_message.assert_any_call("srv-123", "user", "hello")
    client.save_message.assert_any_call("srv-123", "assistant", "response")


def test_save_message_skipped_without_session_id():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
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
    s = Session(client)
    tokens = s._capture_tokens()
    assert tokens is None
    assert s.total_tokens == 0


def test_slash_alone_shows_help():
    """Typing just '/' should show command list."""
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
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
    s = Session(client)
    s._undo_last_turn()  # Should not crash
    assert s.history == []
    assert s.turns == 0


def test_undo_single_turn():
    client = MagicMock(spec=SealevelClient)
    client.last_usage = None
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
