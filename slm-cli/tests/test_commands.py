"""Tests for sealevel_cli.commands — slash command registry, handlers, file helpers."""
import os
import subprocess
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from sealevel_cli.commands import (
    SlashCommand,
    CommandResult,
    build_command_registry,
    _read_file,
    _extract_rust_code,
    _write_code_to_file,
    REVIEW_PROMPT,
    MIGRATE_PROMPT,
    GEN_PROMPT,
    TESTS_PROMPT,
    cmd_review,
    cmd_migrate,
    cmd_gen,
    cmd_tests,
    cmd_explain_tx,
    cmd_explain_error,
    cmd_config,
    cmd_clear,
    cmd_help,
    cmd_exit,
)


# --- Registry ---


def test_registry_has_all_commands():
    cmds = build_command_registry()
    expected = ["/review", "/migrate", "/gen", "/tests", "/explain-tx",
                "/explain-error", "/status", "/usage", "/copy",
                "/sessions", "/resume", "/rename", "/rotate-key",
                "/compact", "/export", "/history",
                "/config", "/clear", "/help", "/exit"]
    for name in expected:
        assert name in cmds
    assert len(cmds) == len(expected)


def test_registry_returns_slash_commands():
    cmds = build_command_registry()
    for cmd in cmds.values():
        assert isinstance(cmd, SlashCommand)
        assert cmd.name.startswith("/")
        assert callable(cmd.handler)


def test_history_commands_flagged():
    cmds = build_command_registry()
    assert cmds["/review"].adds_to_history is True
    assert cmds["/config"].adds_to_history is False
    assert cmds["/clear"].adds_to_history is False
    assert cmds["/help"].adds_to_history is False
    assert cmds["/exit"].adds_to_history is False


def test_file_commands_flagged():
    cmds = build_command_registry()
    assert cmds["/review"].expects_file is True
    assert cmds["/migrate"].expects_file is True
    assert cmds["/tests"].expects_file is True
    assert cmds["/gen"].expects_file is False


# --- File helpers ---


def test_read_file_valid():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("fn main() {}")
        f.flush()
        try:
            assert _read_file(f.name) == "fn main() {}"
        finally:
            os.unlink(f.name)


def test_read_file_not_found():
    assert _read_file("/nonexistent/file.rs") is None


def test_read_file_too_large():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("x" * 1_100_000)
        f.flush()
        try:
            assert _read_file(f.name) is None
        finally:
            os.unlink(f.name)


def test_read_file_sensitive():
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w") as f:
            f.write("SECRET=value")
        assert _read_file(env_path) is None


def test_extract_rust_code_with_block():
    text = "Here is code:\n```rust\nfn main() {}\n```\nDone."
    assert _extract_rust_code(text) == "fn main() {}\n"


def test_extract_rust_code_plain_block():
    text = "```\nfn main() {}\n```"
    assert _extract_rust_code(text) == "fn main() {}\n"


def test_extract_rust_code_no_block():
    text = "fn main() {}"
    assert _extract_rust_code(text) == "fn main() {}"


def test_write_code_to_file():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        path = f.name
    try:
        _write_code_to_file("```rust\nfn main() {}\n```", path)
        with open(path) as f:
            assert f.read() == "fn main() {}\n"
    finally:
        os.unlink(path)


# --- Prompt templates ---


def test_review_prompt_has_placeholder():
    assert "{code}" in REVIEW_PROMPT


def test_migrate_prompt_has_placeholder():
    assert "{code}" in MIGRATE_PROMPT


def test_gen_prompt_has_placeholder():
    assert "{description}" in GEN_PROMPT


def test_tests_prompt_has_placeholder():
    assert "{code}" in TESTS_PROMPT


# --- /review ---


def test_cmd_review_no_args():
    assert cmd_review([], MagicMock()) is None


def test_cmd_review_missing_file():
    assert cmd_review(["/nonexistent.rs"], MagicMock()) is None


def test_cmd_review_streams_and_returns():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("fn main() {}")
        f.flush()
        try:
            session = MagicMock()
            session.stream_response.return_value = "Looks good"
            result = cmd_review([f.name], session)
            assert isinstance(result, CommandResult)
            assert result.assistant_msg == "Looks good"
            assert "fn main()" in result.user_msg
            session.stream_response.assert_called_once()
        finally:
            os.unlink(f.name)


def test_cmd_review_stream_failure():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("code")
        f.flush()
        try:
            session = MagicMock()
            session.stream_response.return_value = None
            assert cmd_review([f.name], session) is None
        finally:
            os.unlink(f.name)


# --- /migrate ---


def test_cmd_migrate_no_args():
    assert cmd_migrate([], MagicMock()) is None


def test_cmd_migrate_no_double_clean():
    """stream_response already cleans — migrate should not re-clean."""
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("old code")
        f.flush()
        try:
            session = MagicMock()
            session.stream_response.return_value = "already cleaned"
            result = cmd_migrate([f.name], session)
            assert result.assistant_msg == "already cleaned"
        finally:
            os.unlink(f.name)


def test_cmd_migrate_write_mode():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("old code")
        f.flush()
        try:
            session = MagicMock()
            session.stream_response.return_value = "```rust\nnew code\n```"
            cmd_migrate([f.name, "--write"], session)
            with open(f.name) as out:
                assert out.read() == "new code\n"
        finally:
            os.unlink(f.name)


# --- /gen ---


def test_cmd_gen_no_args():
    assert cmd_gen([], MagicMock()) is None


def test_cmd_gen_with_description():
    session = MagicMock()
    session.stream_response.return_value = "generated code"
    result = cmd_gen(["counter", "with", "increment"], session)
    assert result is not None
    assert "counter with increment" in result.user_msg


def test_cmd_gen_with_output():
    with tempfile.NamedTemporaryFile(suffix=".rs", delete=False) as f:
        path = f.name
    try:
        session = MagicMock()
        session.stream_response.return_value = "```rust\nfn main() {}\n```"
        cmd_gen(["counter", "-o", path], session)
        with open(path) as out:
            assert out.read() == "fn main() {}\n"
    finally:
        os.unlink(path)


def test_cmd_gen_only_output_flag():
    """Gen with -o but no description shows usage."""
    assert cmd_gen(["-o", "/tmp/out.rs"], MagicMock()) is None


# --- /tests ---


def test_cmd_tests_no_args():
    assert cmd_tests([], MagicMock()) is None


def test_cmd_tests_valid_file():
    with tempfile.NamedTemporaryFile(suffix=".rs", mode="w", delete=False) as f:
        f.write("fn main() {}")
        f.flush()
        try:
            session = MagicMock()
            session.stream_response.return_value = "test code"
            result = cmd_tests([f.name], session)
            assert result.assistant_msg == "test code"
        finally:
            os.unlink(f.name)


# --- /explain-tx ---


def test_cmd_explain_tx_no_args():
    assert cmd_explain_tx([], MagicMock()) is None


def test_cmd_explain_tx_streams():
    session = MagicMock()
    session.client.explain_tx.return_value = iter(["chunk"])
    session.stream_response_raw.return_value = "explanation"
    result = cmd_explain_tx(["5U3abc"], session)
    assert result.assistant_msg == "explanation"
    assert "5U3abc" in result.user_msg


# --- /explain-error ---


def test_cmd_explain_error_no_args():
    assert cmd_explain_error([], MagicMock()) is None


def test_cmd_explain_error_streams():
    session = MagicMock()
    session.client.explain_error.return_value = iter(["chunk"])
    session.stream_response_raw.return_value = "error explanation"
    result = cmd_explain_error(["0x1771"], session)
    assert result.assistant_msg == "error explanation"


# --- /config ---


def test_cmd_config_show():
    session = MagicMock()
    result = cmd_config([], session)
    assert result is None


def test_cmd_config_set_api_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            session = MagicMock()
            cmd_config(["--api-key", "slm_validkey123456789"], session)
            assert session.client.api_key == "slm_validkey123456789"


def test_cmd_config_rejects_bad_key():
    session = MagicMock()
    result = cmd_config(["--api-key", "bad"], session)
    assert result is None
    # api_key should NOT be set on client
    assert not hasattr(session.client, 'api_key') or session.client.api_key != "bad"


def test_cmd_config_set_api_url():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            session = MagicMock()
            cmd_config(["--api-url", "https://custom.api"], session)
            assert session.client.base_url == "https://custom.api"


def test_cmd_config_set_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            session = MagicMock()
            cmd_config(["--mode", "fast"], session)
            # Should not crash


def test_cmd_config_rejects_bad_mode():
    session = MagicMock()
    result = cmd_config(["--mode", "turbo"], session)
    assert result is None


def test_cmd_config_unknown_flag_warns():
    session = MagicMock()
    with patch("sealevel_cli.display.print_warning") as mock_warn:
        cmd_config(["--unknown"], session)
        mock_warn.assert_called_once()
        assert "Unknown flag" in mock_warn.call_args[0][0]


# --- /clear ---


def test_cmd_clear_empties_history():
    session = MagicMock()
    session.history = [{"role": "user", "content": "hi"}]
    cmd_clear([], session)
    assert session.history == []


# --- /exit ---


def test_cmd_exit_raises_system_exit():
    with pytest.raises(SystemExit):
        cmd_exit([], MagicMock())


# --- /help ---


def test_cmd_help_runs():
    session = MagicMock()
    session.commands = build_command_registry()
    assert cmd_help([], session) is None


# --- /status ---


def test_cmd_status_runs():
    from sealevel_cli.commands import cmd_status
    from sealevel_cli.client import HealthResponse
    session = MagicMock()
    session.client.get_health.return_value = HealthResponse("ok", True, False, "2026-01-01")
    result = cmd_status([], session)
    assert result is None


# --- /usage ---


def test_cmd_usage_runs():
    from sealevel_cli.commands import cmd_usage
    from sealevel_cli.client import UsageResponse
    session = MagicMock()
    session.client.get_usage.return_value = UsageResponse("free", 10, 5000, [], [])
    result = cmd_usage([], session)
    assert result is None


def test_cmd_usage_handles_error():
    from sealevel_cli.commands import cmd_usage
    from sealevel_cli.client import SealevelAuthError
    session = MagicMock()
    session.client.get_usage.side_effect = SealevelAuthError("no auth")
    result = cmd_usage([], session)
    assert result is None


# --- /copy ---


def test_cmd_copy_no_history():
    from sealevel_cli.commands import cmd_copy
    session = MagicMock()
    session.history = []
    result = cmd_copy([], session)
    assert result is None


def test_cmd_copy_copies_last_assistant():
    from sealevel_cli.commands import cmd_copy
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    with patch("subprocess.run") as mock_run:
        cmd_copy([], session)
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["input"] == b"Hello!"


def test_cmd_copy_no_assistant_msg():
    from sealevel_cli.commands import cmd_copy
    session = MagicMock()
    session.history = [{"role": "user", "content": "hi"}]
    result = cmd_copy([], session)
    assert result is None


def test_cmd_copy_file_not_found():
    from sealevel_cli.commands import cmd_copy
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    with patch("subprocess.run", side_effect=FileNotFoundError):
        cmd_copy([], session)  # Should not crash


def test_cmd_copy_subprocess_error():
    from sealevel_cli.commands import cmd_copy
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    with patch("subprocess.run", side_effect=subprocess.SubprocessError("fail")):
        cmd_copy([], session)  # Should not crash


# --- Registry includes new commands ---


def test_registry_has_phase1_commands():
    cmds = build_command_registry()
    assert "/status" in cmds
    assert "/usage" in cmds
    assert "/copy" in cmds


def test_registry_has_phase3_commands():
    cmds = build_command_registry()
    assert "/compact" in cmds
    assert "/export" in cmds
    assert "/history" in cmds
    for name in ["/compact", "/export", "/history"]:
        assert cmds[name].adds_to_history is False


def test_registry_has_phase2_commands():
    cmds = build_command_registry()
    assert "/sessions" in cmds
    assert "/resume" in cmds
    assert "/rename" in cmds
    assert "/rotate-key" in cmds
    for name in ["/sessions", "/resume", "/rename", "/rotate-key"]:
        assert cmds[name].adds_to_history is False


# --- /sessions ---


def test_cmd_sessions_runs():
    from sealevel_cli.commands import cmd_sessions
    session = MagicMock()
    session.client.list_sessions.return_value = [
        {"id": "abc123", "title": "Test", "updatedAt": "2026-01-01T00:00:00"}
    ]
    result = cmd_sessions([], session)
    assert result is None


def test_cmd_sessions_empty():
    from sealevel_cli.commands import cmd_sessions
    session = MagicMock()
    session.client.list_sessions.return_value = []
    result = cmd_sessions([], session)
    assert result is None


def test_cmd_sessions_error():
    from sealevel_cli.commands import cmd_sessions
    from sealevel_cli.client import SealevelAuthError
    session = MagicMock()
    session.client.list_sessions.side_effect = SealevelAuthError("no auth")
    result = cmd_sessions([], session)
    assert result is None


# --- /resume ---


def test_cmd_resume_no_args():
    from sealevel_cli.commands import cmd_resume
    session = MagicMock()
    result = cmd_resume([], session)
    assert result is None


def test_cmd_resume_loads_session():
    from sealevel_cli.commands import cmd_resume
    session = MagicMock()
    session.client.get_session.return_value = {
        "id": "abc123",
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    }
    session.history = []
    cmd_resume(["abc123"], session)
    assert len(session.history) == 2
    assert session.session_id == "abc123"


def test_cmd_resume_error():
    from sealevel_cli.commands import cmd_resume
    from sealevel_cli.client import SealevelConnectionError
    session = MagicMock()
    session.client.get_session.side_effect = SealevelConnectionError("not found")
    session.history = []
    cmd_resume(["bad-id"], session)
    assert session.history == []  # Should not modify history


# --- /rename ---


def test_cmd_rename_no_args():
    from sealevel_cli.commands import cmd_rename
    session = MagicMock()
    result = cmd_rename([], session)
    assert result is None


def test_cmd_rename_no_session():
    from sealevel_cli.commands import cmd_rename
    session = MagicMock()
    session.session_id = None
    result = cmd_rename(["new name"], session)
    assert result is None


def test_cmd_rename_works():
    from sealevel_cli.commands import cmd_rename
    session = MagicMock()
    session.session_id = "abc123"
    cmd_rename(["PDA", "exploration"], session)
    session.client.rename_session.assert_called_once_with("abc123", "PDA exploration")


def test_cmd_rename_error():
    from sealevel_cli.commands import cmd_rename
    from sealevel_cli.client import SealevelConnectionError
    session = MagicMock()
    session.session_id = "abc123"
    session.client.rename_session.side_effect = SealevelConnectionError("fail")
    cmd_rename(["new name"], session)  # Should not crash


# --- /rotate-key ---


def test_cmd_rotate_key():
    from sealevel_cli.commands import cmd_rotate_key
    session = MagicMock()
    session.client.rotate_key.return_value = "slm_newkey1234567890"
    with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": "/tmp/test"}):
        with patch("sealevel_cli.config.set_value") as mock_set:
            cmd_rotate_key([], session)
            mock_set.assert_called_once()
            assert session.client.api_key == "slm_newkey1234567890"


# --- /compact ---


def test_cmd_compact_default():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    cmd_compact([], session)
    assert len(session.history) == 10  # 5 turns * 2


def test_cmd_compact_custom_turns():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    cmd_compact(["3"], session)
    assert len(session.history) == 6  # 3 turns * 2


def test_cmd_compact_empty_history():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = []
    cmd_compact([], session)  # Should not crash


def test_cmd_compact_small_history():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    cmd_compact([], session)
    assert len(session.history) == 2  # Already smaller than 5 turns


def test_cmd_compact_zero_turns():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    cmd_compact(["0"], session)
    assert len(session.history) == 2  # Clamped to 1 turn


def test_cmd_compact_negative_turns():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    cmd_compact(["-5"], session)
    assert len(session.history) == 2  # Clamped to 1 turn


def test_cmd_compact_invalid_arg():
    from sealevel_cli.commands import cmd_compact
    session = MagicMock()
    session.history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
    cmd_compact(["abc"], session)  # Should use default 5
    assert len(session.history) == 10


# --- /export ---


def test_cmd_export_writes_file():
    from sealevel_cli.commands import cmd_export
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    path = "test-export-output.md"
    try:
        cmd_export([path], session)
        with open(path) as f:
            content = f.read()
        assert "## USER" in content
        assert "## ASSISTANT" in content
        assert "hi" in content
        assert "hello" in content
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_cmd_export_empty_history():
    from sealevel_cli.commands import cmd_export
    session = MagicMock()
    session.history = []
    result = cmd_export([], session)
    assert result is None


def test_cmd_export_outside_cwd():
    from sealevel_cli.commands import cmd_export
    session = MagicMock()
    session.history = [{"role": "user", "content": "test"}]
    cmd_export(["/etc/evil.md"], session)  # Should be rejected


def test_cmd_export_permission_error():
    from sealevel_cli.commands import cmd_export
    session = MagicMock()
    session.history = [{"role": "user", "content": "test"}]
    with patch("builtins.open", side_effect=PermissionError("denied")):
        cmd_export(["/root/nope.md"], session)  # Should not crash


def test_cmd_export_filename_format():
    from sealevel_cli.commands import cmd_export
    import re as _re
    session = MagicMock()
    session.history = [{"role": "user", "content": "test"}]
    cmd_export([], session)
    import glob
    files = glob.glob("sealevel-*.md")
    assert len(files) >= 1
    for f in files:
        assert _re.match(r"sealevel-\d{8}-\d{6}\.md", f)
        os.unlink(f)


def test_cmd_export_default_filename():
    from sealevel_cli.commands import cmd_export
    session = MagicMock()
    session.history = [{"role": "user", "content": "test"}]
    cmd_export([], session)
    # Should create a file with sealevel-*.md pattern
    import glob
    files = glob.glob("sealevel-*.md")
    assert len(files) >= 1
    for f in files:
        os.unlink(f)


# --- /history ---


def test_cmd_history_empty():
    from sealevel_cli.commands import cmd_history
    session = MagicMock()
    session.history = []
    result = cmd_history([], session)
    assert result is None


def test_cmd_history_with_messages():
    from sealevel_cli.commands import cmd_history
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    result = cmd_history([], session)
    assert result is None


def test_cmd_history_truncates_long_content():
    from sealevel_cli.commands import cmd_history
    session = MagicMock()
    session.history = [
        {"role": "user", "content": "x" * 200},
        {"role": "assistant", "content": "y" * 200},
    ]
    cmd_history([], session)  # Should truncate at 80 chars


# --- /rotate-key ---


def test_cmd_rotate_key_empty_response():
    from sealevel_cli.commands import cmd_rotate_key
    session = MagicMock()
    session.client.rotate_key.return_value = ""
    cmd_rotate_key([], session)  # Should print error, not crash


def test_cmd_rotate_key_error():
    from sealevel_cli.commands import cmd_rotate_key
    from sealevel_cli.client import SealevelAuthError
    session = MagicMock()
    session.client.rotate_key.side_effect = SealevelAuthError("no auth")
    cmd_rotate_key([], session)  # Should not crash
