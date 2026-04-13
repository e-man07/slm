"""
Feature 22: Python CLI - Config management tests

RED  - tests expect config module with load/save/get/set
GREEN - implement slm_cli/config.py
"""
import os
import tempfile
import pytest
from pathlib import Path


def test_config_module_importable():
    from slm_cli import config
    assert hasattr(config, "load_config")
    assert hasattr(config, "save_config")
    assert hasattr(config, "get_value")
    assert hasattr(config, "set_value")


def test_load_config_returns_dict():
    from slm_cli.config import load_config

    with tempfile.TemporaryDirectory() as tmpdir:
        config = load_config(config_dir=tmpdir)
        assert isinstance(config, dict)


def test_save_and_load_config():
    from slm_cli.config import load_config, save_config

    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "slm_test123", "api_url": "https://slm.dev/api"}, config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_key"] == "slm_test123"
        assert config["api_url"] == "https://slm.dev/api"


def test_set_value():
    from slm_cli.config import load_config, save_config, set_value

    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({}, config_dir=tmpdir)
        set_value("api_key", "slm_newkey", config_dir=tmpdir)
        config = load_config(config_dir=tmpdir)
        assert config["api_key"] == "slm_newkey"


def test_get_value():
    from slm_cli.config import save_config, get_value

    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "slm_mykey"}, config_dir=tmpdir)
        assert get_value("api_key", config_dir=tmpdir) == "slm_mykey"


def test_get_value_returns_none_for_missing():
    from slm_cli.config import get_value

    with tempfile.TemporaryDirectory() as tmpdir:
        assert get_value("nonexistent", config_dir=tmpdir) is None


def test_config_file_created_in_correct_location():
    from slm_cli.config import save_config

    with tempfile.TemporaryDirectory() as tmpdir:
        save_config({"api_key": "test"}, config_dir=tmpdir)
        config_file = Path(tmpdir) / "config.toml"
        assert config_file.exists()


def test_default_config_values():
    from slm_cli.config import DEFAULT_CONFIG
    assert "api_url" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["api_url"] == "https://slm.dev/api"
