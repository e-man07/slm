"""
Feature 22: Python CLI - Display formatting tests

RED  - tests expect display module with rich formatting helpers
GREEN - implement slm_cli/display.py
"""
import pytest


def test_display_module_importable():
    from slm_cli import display
    assert hasattr(display, "format_error_result")
    assert hasattr(display, "format_markdown")
    assert hasattr(display, "create_spinner")


def test_format_error_result():
    from slm_cli.display import format_error_result
    result = format_error_result(
        program="Anchor Framework",
        name="ConstraintMut",
        code=2000,
        hex_code="0x7D0",
        message="A mut constraint was violated",
    )
    assert "Anchor Framework" in result
    assert "ConstraintMut" in result
    assert "2000" in result
    assert "0x7D0" in result
    assert "mut constraint" in result


def test_format_error_result_unknown():
    from slm_cli.display import format_error_result
    result = format_error_result(
        program="Unknown",
        name="CustomError[5]",
        code=6005,
        hex_code="0x1775",
        message="Custom error",
    )
    assert "Unknown" in result
    assert "6005" in result


def test_format_markdown_returns_string():
    from slm_cli.display import format_markdown
    result = format_markdown("# Hello\n\nThis is **bold** text.")
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_spinner():
    from slm_cli.display import create_spinner
    spinner = create_spinner("Loading...")
    # Should return a rich Status or similar context manager
    assert spinner is not None
    assert hasattr(spinner, "__enter__") or hasattr(spinner, "start")
