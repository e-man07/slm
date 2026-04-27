"""Tests for sealevel_cli.config — TOML config, keyring, get/set/clear values."""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from sealevel_cli.config import (
    DEFAULT_CONFIG,
    load_config,
    save_config,
    get_value,
    set_value,
    clear_value,
    _parse_toml,
    _to_toml,
    _get_config_dir,
    _config_file,
)


# --- Module basics ---


def test_config_module_importable():
    from sealevel_cli import config
    assert hasattr(config, "load_config")
    assert hasattr(config, "save_config")
    assert hasattr(config, "get_value")
    assert hasattr(config, "set_value")


def test_default_config_values():
    assert "api_url" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["api_url"] == "https://www.sealevel.tech"
    assert DEFAULT_CONFIG["mode"] == "quality"


# --- Config dir resolution ---


def test_get_config_dir_explicit():
    result = _get_config_dir("/tmp/custom")
    assert result == Path("/tmp/custom")


def test_get_config_dir_from_env():
    with patch.dict(os.environ, {"SEALEVEL_CONFIG_DIR": "/tmp/env-config"}):
        result = _get_config_dir()
        assert result == Path("/tmp/env-config")


def test_get_config_dir_default():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("SEALEVEL_CONFIG_DIR", None)
        result = _get_config_dir()
        assert result == Path.home() / ".sealevel"


def test_config_file_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _config_file(tmpdir)
        assert result == Path(tmpdir) / "config.toml"


# --- TOML parser ---


def test_parse_toml_basic():
    text = 'api_url = "https://www.sealevel.tech"\nmode = "quality"'
    result = _parse_toml(text)
    assert result == {"api_url": "https://www.sealevel.tech", "mode": "quality"}


def test_parse_toml_single_quotes():
    text = "api_key = 'slm_test123'"
    result = _parse_toml(text)
    assert result == {"api_key": "slm_test123"}


def test_parse_toml_skips_comments():
    text = "# This is a comment\napi_url = \"https://test.com\"\n# Another comment"
    result = _parse_toml(text)
    assert result == {"api_url": "https://test.com"}


def test_parse_toml_skips_empty_lines():
    text = "\n\napi_url = \"https://test.com\"\n\n"
    result = _parse_toml(text)
    assert result == {"api_url": "https://test.com"}


def test_parse_toml_strips_whitespace():
    text = "  api_url  =  \"https://test.com\"  "
    result = _parse_toml(text)
    assert result == {"api_url": "https://test.com"}


def test_to_toml_basic():
    data = {"api_url": "https://test.com", "mode": "quality"}
    result = _to_toml(data)
    assert 'api_url = "https://test.com"' in result
    assert 'mode = "quality"' in result


def test_to_toml_sorted_keys():
    data = {"z_key": "z", "a_key": "a"}
    result = _to_toml(data)
    lines = result.strip().split("\n")
    assert lines[0].startswith("a_key")
    assert lines[1].startswith("z_key")


def test_toml_roundtrip():
    original = {"api_url": "https://www.sealevel.tech", "mode": "fast"}
    serialized = _to_toml(original)
    parsed = _parse_toml(serialized)
    assert parsed == original


# --- Load / save config ---


def test_load_config_returns_dict():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=tmpdir)
        assert isinstance(config, dict)


def test_load_config_returns_defaults_when_no_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=tmpdir)
        assert config["api_url"] == "https://www.sealevel.tech"
        assert config["mode"] == "quality"


def test_save_and_load_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "slm_test123", "api_url": "https://custom.api"}, config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_key"] == "slm_test123"
        assert config["api_url"] == "https://custom.api"


def test_save_creates_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "nested", "dir")
        save_config({"key": "val"}, config_dir=nested)
        assert Path(nested, "config.toml").exists()


def test_load_config_merges_with_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"custom_key": "custom_val"}, config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_url"] == "https://www.sealevel.tech"
        assert config["custom_key"] == "custom_val"


def test_load_config_overrides_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_url": "https://override.api", "mode": "fast"}, config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_url"] == "https://override.api"
        assert config["mode"] == "fast"


def test_config_file_created_in_correct_location():
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "test"}, config_dir=tmpdir)
        config_file = Path(tmpdir) / "config.toml"
        assert config_file.exists()


# --- get/set/clear values ---


def test_set_value():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            save_config({}, config_dir=tmpdir)
            set_value("api_key", "slm_newkey", config_dir=tmpdir)
            config = load_config(config_dir=tmpdir)
            assert config["api_key"] == "slm_newkey"


def test_get_value():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            save_config({"api_key": "slm_mykey"}, config_dir=tmpdir)
            assert get_value("api_key", config_dir=tmpdir) == "slm_mykey"


def test_get_value_returns_none_for_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert get_value("nonexistent", config_dir=tmpdir) is None


def test_set_value_overwrites():
    with tempfile.TemporaryDirectory() as tmpdir:
        set_value("mode", "quality", config_dir=tmpdir)
        set_value("mode", "fast", config_dir=tmpdir)
        assert get_value("mode", config_dir=tmpdir) == "fast"


def test_clear_value():
    with tempfile.TemporaryDirectory() as tmpdir:
        set_value("api_url", "https://custom.api", config_dir=tmpdir)
        clear_value("api_url", config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_url"] == "https://www.sealevel.tech"


def test_set_value_preserves_other_keys():
    with tempfile.TemporaryDirectory() as tmpdir:
        set_value("api_url", "https://one.api", config_dir=tmpdir)
        set_value("mode", "fast", config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_url"] == "https://one.api"
        assert config["mode"] == "fast"


# --- Keyring integration ---


def test_set_value_tries_keyring_for_secrets():
    """When keyring is available, api_key should go to keyring, not TOML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_keyring = MagicMock()
        mock_keyring.set_password = MagicMock(return_value=None)
        with patch.dict("sys.modules", {"keyring": mock_keyring}):
            set_value("api_key", "slm_secret123", config_dir=tmpdir)
            mock_keyring.set_password.assert_called_once()


def test_set_value_falls_back_to_toml_without_keyring():
    """When keyring is not available, api_key should go to TOML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            set_value("api_key", "slm_fallback", config_dir=tmpdir)
            config = load_config(config_dir=tmpdir)
            assert config["api_key"] == "slm_fallback"


def test_non_secret_keys_skip_keyring():
    """Non-secret keys like 'mode' should always go to TOML, never keyring."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=True):
            set_value("mode", "fast", config_dir=tmpdir)
            config = load_config(config_dir=tmpdir)
            assert config["mode"] == "fast"


def test_clear_value_api_key_calls_keyring_delete():
    """Clearing api_key should delete from keyring when available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=True):
            with patch("sealevel_cli.config._keyring_delete") as mock_del:
                clear_value("api_key", config_dir=tmpdir)
                mock_del.assert_called_once()


def test_keyring_get_returns_none_on_error():
    """Keyring errors should return None, not crash."""
    with patch("sealevel_cli.config._keyring_available", return_value=True):
        with patch("sealevel_cli.config._keyring_get", return_value=None):
            with tempfile.TemporaryDirectory() as tmpdir:
                result = get_value("api_key", config_dir=tmpdir)
                assert result is None


def test_keyring_set_failure_falls_to_toml():
    """If keyring set fails, should fall back to TOML."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=True):
            with patch("sealevel_cli.config._keyring_set", return_value=False):
                set_value("api_key", "slm_fallback99999999", config_dir=tmpdir)
                config = load_config(config_dir=tmpdir)
                assert config["api_key"] == "slm_fallback99999999"


def test_keyring_delete_error_no_crash():
    """Keyring delete error should not crash (handled internally)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=True):
            # _keyring_delete internally catches all exceptions
            clear_value("api_key", config_dir=tmpdir)  # Should not crash


def test_clear_value_api_key_also_clears_toml():
    """Clearing api_key should remove from TOML too."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("sealevel_cli.config._keyring_available", return_value=False):
            set_value("api_key", "slm_toremove12345", config_dir=tmpdir)
            assert get_value("api_key", config_dir=tmpdir) == "slm_toremove12345"
            clear_value("api_key", config_dir=tmpdir)
            assert get_value("api_key", config_dir=tmpdir) is None


# --- Fix #2: Config file permissions ---


def test_save_config_restricts_permissions():
    """Config file should be chmod 600 (user-only read/write)."""
    import stat
    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "slm_secret12345"}, config_dir=tmpdir)
        config_path = Path(tmpdir) / "config.toml"
        mode = config_path.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
