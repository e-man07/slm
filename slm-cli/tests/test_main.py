"""
Feature 22: Python CLI - Main CLI entry point tests

RED  - tests expect the main typer app with expected commands
GREEN - implement slm_cli/main.py
"""
import pytest
from typer.testing import CliRunner


def test_main_module_importable():
    from slm_cli.main import app
    assert app is not None


def test_cli_help():
    from slm_cli.main import app
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "SLM" in result.stdout or "slm" in result.stdout.lower()


def test_config_show_without_config():
    from slm_cli.main import app
    runner = CliRunner()
    result = runner.invoke(app, ["config", "--show"])
    # Should not crash even without a config file
    assert result.exit_code == 0


def test_config_set_api_key():
    import tempfile
    import os
    from slm_cli.main import app

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmpdir:
        env = {**os.environ, "SLM_CONFIG_DIR": tmpdir}
        result = runner.invoke(app, ["config", "--api-key", "slm_test999"], env=env)
        assert result.exit_code == 0
        assert "saved" in result.stdout.lower() or "set" in result.stdout.lower() or "slm_test999" in result.stdout
