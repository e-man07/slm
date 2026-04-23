"""Tests for sealevel_cli.main — entry point, session launch, config subcommand."""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from sealevel_cli.main import app


runner = CliRunner()


# --- Entry point ---


def test_main_module_importable():
    from sealevel_cli.main import app
    assert app is not None


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Sealevel" in result.stdout


def test_cli_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "SEALEVEL" in result.stdout
    assert "0.1.0" in result.stdout


def test_bare_slm_starts_session():
    with patch("sealevel_cli.session.Session.run"):
        result = runner.invoke(app, [])
        assert result.exit_code == 0


def test_help_shows_config_command():
    result = runner.invoke(app, ["--help"])
    assert "config" in result.stdout


def test_help_does_not_show_legacy_commands():
    """Legacy subcommands removed — only config visible."""
    result = runner.invoke(app, ["--help"])
    assert "review" not in result.stdout.lower().split("config")[0]
    assert "migrate" not in result.stdout.lower().split("config")[0]


# --- Config subcommand ---


def test_config_show():
    result = runner.invoke(app, ["config", "--show"])
    assert result.exit_code == 0
    assert "CONFIG" in result.stdout


def test_config_set_api_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        result = runner.invoke(app, ["config", "--api-key", "slm_test999abcdef1234"], env=env)
        assert result.exit_code == 0
        assert "✓" in result.stdout


def test_config_rejects_short_api_key():
    result = runner.invoke(app, ["config", "--api-key", "slm_short"])
    assert result.exit_code == 1


def test_config_rejects_wrong_prefix():
    result = runner.invoke(app, ["config", "--api-key", "sk_wrongprefix12345678"])
    assert result.exit_code == 1


def test_config_set_api_url():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        result = runner.invoke(app, ["config", "--api-url", "https://custom.api"], env=env)
        assert result.exit_code == 0
        assert "✓" in result.stdout


def test_config_set_mode_quality():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        result = runner.invoke(app, ["config", "--mode", "quality"], env=env)
        assert result.exit_code == 0


def test_config_set_mode_fast():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        result = runner.invoke(app, ["config", "--mode", "fast"], env=env)
        assert result.exit_code == 0


def test_config_rejects_invalid_mode():
    result = runner.invoke(app, ["config", "--mode", "turbo"])
    assert result.exit_code == 1


def test_config_no_args_shows_hint():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "--show" in result.stdout


def test_config_show_masks_api_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        runner.invoke(app, ["config", "--api-key", "slm_supersecretkey1234"], env=env)
        result = runner.invoke(app, ["config", "--show"], env=env)
        assert result.exit_code == 0
        # Full key should not appear
        assert "slm_supersecretkey1234" not in result.stdout or "···" in result.stdout


# --- No-API-key warning ---


# --- Pipe mode (-p) ---


def test_pipe_mode():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        from sealevel_cli.config import set_value
        set_value("api_key", "slm_testkey12345678", config_dir=tmpdir)

        with patch("sealevel_cli.client.httpx.stream") as mock_stream:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines.return_value = iter([
                'data: {"choices":[{"delta":{"content":"PDA answer"}}]}',
                'data: [DONE]',
            ])
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_stream.return_value = mock_resp

            result = runner.invoke(app, ["-p", "what is PDA?"], env=env)
            assert result.exit_code == 0
            assert "PDA answer" in result.stdout


def test_pipe_mode_with_stdin():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        from sealevel_cli.config import set_value
        set_value("api_key", "slm_testkey12345678", config_dir=tmpdir)

        with patch("sealevel_cli.client.httpx.stream") as mock_stream:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
            mock_resp.iter_lines.return_value = iter([
                'data: {"choices":[{"delta":{"content":"Reviewed!"}}]}',
                'data: [DONE]',
            ])
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_stream.return_value = mock_resp

            # Simulate piped stdin
            result = runner.invoke(app, ["-p", "review this"], input="fn main() {}", env=env)
            assert result.exit_code == 0


def test_pipe_mode_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        from sealevel_cli.config import set_value
        set_value("api_key", "slm_testkey12345678", config_dir=tmpdir)

        with patch("sealevel_cli.client.httpx.stream", side_effect=Exception("fail")):
            result = runner.invoke(app, ["-p", "test"], env=env)
            assert result.exit_code == 1


def test_continue_flag_with_sessions():
    with patch("sealevel_cli.session.Session.run"):
        with patch("sealevel_cli.client.SealevelClient.list_sessions") as mock_list:
            mock_list.return_value = [{"id": "sess-1", "title": "Test"}]
            with patch("sealevel_cli.session.Session.from_server") as mock_from:
                mock_instance = MagicMock()
                mock_from.return_value = mock_instance
                result = runner.invoke(app, ["-c"])
                assert result.exit_code == 0


def test_continue_flag_no_sessions():
    with patch("sealevel_cli.client.SealevelClient.list_sessions") as mock_list:
        mock_list.return_value = []
        result = runner.invoke(app, ["-c"])
        assert "No previous sessions" in result.stdout


def test_pipe_mode_help():
    result = runner.invoke(app, ["--help"])
    assert "-p" in result.stdout or "--prompt" in result.stdout


# --- No-API-key warning ---


def test_session_warns_no_api_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            with patch("sealevel_cli.session.Session.run"):
                result = runner.invoke(app, [], env=env)
                assert "No API key" in result.stdout or "sealevel.tech" in result.stdout
