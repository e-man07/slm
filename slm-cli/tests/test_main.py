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
    from sealevel_cli import __version__
    assert __version__ in result.stdout


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


def test_config_rejects_non_http_url_typer():
    """Fix #4: slm config --api-url should validate like /config does."""
    result = runner.invoke(app, ["config", "--api-url", "ftp://bad.url"])
    assert result.exit_code == 1


def test_config_rejects_empty_url_typer():
    result = runner.invoke(app, ["config", "--api-url", ""])
    assert result.exit_code == 1


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


def test_config_show_includes_keyring_key():
    """Fix #3: slm config --show should display key from keyring."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        # Set key via config (stored in TOML since test env has no keyring)
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            from sealevel_cli.config import set_value as _sv
            _sv("api_key", "slm_fromkeyring12345", config_dir=tmpdir)
        result = runner.invoke(app, ["config", "--show"], env=env)
        assert result.exit_code == 0
        # Should show masked version of key
        assert "API KEY" in result.stdout or "slm_from" in result.stdout


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


# --- Onboarding ---


def test_first_run_setup_browser_login():
    """Choice 1: browser device flow."""
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", return_value="1"):
            with patch("sealevel_cli.main._device_login_flow"):
                with patch("sealevel_cli.main.get_value", return_value="slm_fromdevice12345"):
                    key = _first_run_setup(tmpdir)
        assert key == "slm_fromdevice12345"


def test_first_run_setup_paste_key():
    """Choice 2: manual key paste."""
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", side_effect=["2", "slm_valid1234567890ab"]):
            key = _first_run_setup(tmpdir)
        assert key == "slm_valid1234567890ab"


def test_first_run_setup_paste_invalid_key():
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", side_effect=["2", "bad_key"]):
            key = _first_run_setup(tmpdir)
        assert key is None


def test_first_run_setup_paste_empty():
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", side_effect=["2", ""]):
            key = _first_run_setup(tmpdir)
        assert key is None


def test_first_run_setup_invalid_choice():
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", return_value="3"):
            key = _first_run_setup(tmpdir)
        assert key is None


def test_first_run_setup_browser_login_error():
    """Browser login failure returns None."""
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", return_value="1"):
            with patch("sealevel_cli.main._device_login_flow", side_effect=SystemExit(1)):
                key = _first_run_setup(tmpdir)
        assert key is None


def test_first_run_setup_keyboard_interrupt():
    from sealevel_cli.main import _first_run_setup
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.main.pt_prompt", side_effect=KeyboardInterrupt):
            key = _first_run_setup(tmpdir)
        assert key is None


# --- No-API-key warning ---


def test_session_warns_no_api_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            with patch("sealevel_cli.session.Session.run"):
                result = runner.invoke(app, [], env=env)
                assert "No API key" in result.stdout or "sealevel.tech" in result.stdout


# --- Issue #10/11: mode config wired to client ---


def test_make_client_passes_mode():
    """Client should receive mode from config."""
    from sealevel_cli.main import _make_client
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {"SEALEVEL_CONFIG_DIR": tmpdir}
        with patch.dict(os.environ, env):
            from sealevel_cli.config import set_value
            set_value("mode", "fast", config_dir=tmpdir)
            set_value("api_key", "slm_test1234567890ab", config_dir=tmpdir)
            client = _make_client(quiet=True)
            assert client.mode == "fast"


def test_make_client_default_mode():
    """Client defaults to 'quality' mode."""
    from sealevel_cli.main import _make_client
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {"SEALEVEL_CONFIG_DIR": tmpdir}
        with patch.dict(os.environ, env):
            from sealevel_cli.config import set_value
            set_value("api_key", "slm_test1234567890ab", config_dir=tmpdir)
            client = _make_client(quiet=True)
            assert client.mode == "quality"


# --- slm login ---


def test_login_command_exists():
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "login" in result.stdout.lower() or "device" in result.stdout.lower()


def test_login_initiates_device_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        with patch("sealevel_cli.main._device_login_flow") as mock_flow:
            mock_flow.return_value = None
            result = runner.invoke(app, ["login"], env=env)
            mock_flow.assert_called_once()


# --- slm logout ---


def test_logout_command_exists():
    result = runner.invoke(app, ["logout", "--help"])
    assert result.exit_code == 0


def test_logout_clears_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        from sealevel_cli.config import set_value
        set_value("api_key", "slm_test1234567890ab", config_dir=tmpdir)
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            result = runner.invoke(app, ["logout"], env=env)
            assert result.exit_code == 0
            from sealevel_cli.config import get_value
            assert get_value("api_key", config_dir=tmpdir) is None


def test_logout_when_not_logged_in():
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SEALEVEL_CONFIG_DIR": tmpdir}
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            result = runner.invoke(app, ["logout"], env=env)
            assert result.exit_code == 0
            assert "Not logged in" in result.stdout


# --- _device_login_flow functional tests ---


def test_device_login_flow_success():
    """Full happy path: initiate -> poll -> complete -> save key."""
    from sealevel_cli.main import _device_login_flow
    from sealevel_cli.config import get_value as _get_value
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            with patch("sealevel_cli.client.httpx.post") as mock_post:
                mock_post.return_value = MagicMock(
                    status_code=200,
                    json=lambda: {
                        "userCode": "TEST-1234",
                        "verificationUrl": "https://sealevel.tech/device",
                        "interval": 0,
                        "expiresIn": 30,
                    },
                )
                with patch("sealevel_cli.client.httpx.get") as mock_get:
                    mock_get.return_value = MagicMock(
                        status_code=200,
                        json=lambda: {
                            "status": "complete",
                            "apiKey": "slm_deviceflow12345678",
                            "user": {"name": "testuser", "tier": "free"},
                        },
                    )
                    with patch("webbrowser.open"):
                        with patch("time.sleep"):
                            _device_login_flow()
            key = _get_value("api_key", config_dir=tmpdir)
            assert key == "slm_deviceflow12345678"


def test_device_login_flow_polls_until_complete():
    """Polls pending -> pending -> complete."""
    from sealevel_cli.main import _device_login_flow
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            with patch("sealevel_cli.client.httpx.post") as mock_post:
                mock_post.return_value = MagicMock(
                    status_code=200,
                    json=lambda: {
                        "userCode": "POLL-TEST",
                        "verificationUrl": "https://sealevel.tech/device",
                        "interval": 0,
                        "expiresIn": 30,
                    },
                )
                poll_count = 0
                def make_poll_response():
                    nonlocal poll_count
                    poll_count += 1
                    if poll_count < 3:
                        return {"status": "pending"}
                    return {
                        "status": "complete",
                        "apiKey": "slm_afterpolling12345",
                        "user": {"name": "polled", "tier": "free"},
                    }

                with patch("sealevel_cli.client.httpx.get") as mock_get:
                    mock_resp = MagicMock(status_code=200)
                    mock_resp.json = make_poll_response
                    mock_get.return_value = mock_resp
                    with patch("webbrowser.open"):
                        with patch("time.sleep"):
                            _device_login_flow()
            assert poll_count == 3


def test_device_login_flow_initiate_failure():
    """initiate_device_auth fails -> prints error, exits."""
    from sealevel_cli.main import _device_login_flow
    import click
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            with patch("sealevel_cli.client.httpx.post") as mock_post:
                mock_post.return_value = MagicMock(status_code=500)
                with pytest.raises((SystemExit, click.exceptions.Exit)):
                    _device_login_flow()


def test_device_login_flow_keyboard_interrupt():
    """Ctrl+C during poll prints cancel message and exits."""
    from sealevel_cli.main import _device_login_flow
    import click
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": tmpdir}):
            with patch("sealevel_cli.client.httpx.post") as mock_post:
                mock_post.return_value = MagicMock(
                    status_code=200,
                    json=lambda: {
                        "userCode": "CTRL-TEST",
                        "verificationUrl": "https://sealevel.tech/device",
                        "interval": 0,
                        "expiresIn": 30,
                    },
                )
                with patch("sealevel_cli.client.httpx.get", side_effect=KeyboardInterrupt):
                    with patch("webbrowser.open"):
                        with patch("time.sleep"):
                            with pytest.raises((SystemExit, click.exceptions.Exit)):
                                _device_login_flow()
