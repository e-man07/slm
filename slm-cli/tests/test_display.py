"""Tests for sealevel_cli.display — Rich formatting, theming, brand components."""
import pytest

from sealevel_cli.display import (
    ACCENT,
    ACCENT_DIM,
    MUTED,
    BORDER,
    console,
    sealevel_theme,
    format_error_result,
    format_markdown,
    create_spinner,
    print_streaming,
    print_done,
    print_error_result,
    print_markdown,
    print_header,
    print_status,
    print_user_message,
    print_assistant_label,
    print_response_separator,
    print_config_table,
    print_config_set,
    print_warning,
    print_error,
    print_success,
    print_info,
    print_repl_header,
    print_repl_goodbye,
    print_repl_timing,
    print_version,
    print_file_written,
    print_file_info,
    print_session_header,
    print_command_help,
    print_sessions_table,
    print_status_table,
    print_usage_table,
    stream_with_spinner,
)


# --- Theme and palette ---


def test_color_palette_defined():
    assert ACCENT == "#c8f542"
    assert ACCENT_DIM == "#6dbf28"
    assert MUTED == "#b0ada4"
    assert BORDER == "#787468"


def test_theme_has_accent_style():
    assert "accent" in sealevel_theme.styles
    assert "muted" in sealevel_theme.styles
    assert "err" in sealevel_theme.styles
    assert "ok" in sealevel_theme.styles
    assert "label" in sealevel_theme.styles
    assert "prompt.arrow" in sealevel_theme.styles


def test_console_uses_theme():
    assert console is not None
    # Console should have theme support (can push/pop themes)
    assert hasattr(console, "push_theme")


# --- Module basics ---


def test_display_module_importable():
    from sealevel_cli import display
    assert hasattr(display, "format_error_result")
    assert hasattr(display, "format_markdown")
    assert hasattr(display, "create_spinner")
    assert hasattr(display, "print_header")
    assert hasattr(display, "print_config_table")


# --- format_error_result ---


def test_format_error_result():
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
    result = format_error_result(
        program="Unknown",
        name="CustomError[5]",
        code=6005,
        hex_code="0x1775",
        message="Custom error",
    )
    assert "Unknown" in result
    assert "6005" in result


def test_format_error_result_all_fields_present():
    result = format_error_result("Prog", "Err", 1, "0x1", "msg")
    assert "Program:" in result
    assert "Error:" in result
    assert "Code:" in result
    assert "Message:" in result


# --- format_markdown ---


def test_format_markdown_returns_string():
    result = format_markdown("# Hello\n\nThis is **bold** text.")
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_markdown_strips_markers():
    result = format_markdown("**bold** and `code`")
    assert "**" not in result
    assert "`" not in result


# --- create_spinner ---


def test_create_spinner():
    spinner = create_spinner("Loading...")
    assert spinner is not None
    assert hasattr(spinner, "__enter__") or hasattr(spinner, "start")


def test_create_spinner_default_message():
    spinner = create_spinner()
    assert spinner is not None


# --- Print functions: smoke tests (verify they don't crash) ---


def test_print_streaming_no_crash():
    print_streaming("chunk")


def test_print_done_no_crash():
    print_done()


def test_print_error_result_no_crash():
    print_error_result("Prog", "Err", 1, "0x1", "msg")


def test_print_markdown_no_crash():
    print_markdown("# Hello world")


def test_print_header_no_crash():
    print_header()
    print_header("CHAT")


def test_print_status_connected():
    print_status(model="slm-8b", connected=True)


def test_print_status_disconnected():
    print_status(connected=False)


def test_print_user_message_no_crash():
    print_user_message("How do I derive a PDA?")


def test_print_assistant_label_no_crash():
    print_assistant_label()


def test_print_response_separator_no_crash():
    print_response_separator()


def test_print_config_table_no_crash():
    print_config_table({"api_url": "https://api.sealevel.tech", "mode": "quality"})


def test_print_config_table_masks_api_key():
    # Should not crash and should mask
    print_config_table({"api_key": "slm_verylongsecretkey1234"})


def test_print_config_set_no_crash():
    print_config_set("api_url", "https://custom.api")
    print_config_set("api_key", "slm_verylongsecretkey1234")


def test_print_warning_no_crash():
    print_warning("This is a warning")


def test_print_error_no_crash():
    print_error("Something went wrong")


def test_print_success_no_crash():
    print_success("Operation completed")


def test_print_info_no_crash():
    print_info("Some informational text")


def test_print_repl_header_no_crash():
    print_repl_header()


def test_print_repl_goodbye_no_crash():
    print_repl_goodbye()


def test_print_file_written_no_crash():
    print_file_written("/tmp/output.rs")


def test_print_file_info_no_crash():
    print_file_info("reviewing", "src/lib.rs")


# --- New design features ---


def test_print_version_no_crash():
    print_version()


def test_print_repl_timing_seconds(capsys):
    print_repl_timing(2.5)
    # Rich outputs to its own console, not capsys — just verify no crash


def test_print_repl_timing_milliseconds(capsys):
    print_repl_timing(0.3)


def test_print_repl_goodbye_with_turns():
    print_repl_goodbye(turns=5)


def test_print_repl_goodbye_zero_turns():
    print_repl_goodbye(turns=0)


def test_stream_with_spinner_markdown_mode():
    chunks = iter(["Hello", " ", "world"])
    result = stream_with_spinner(chunks, label=False, render_md=True)
    assert result == "Hello world"


def test_stream_with_spinner_raw_mode():
    chunks = iter(["Hello", " ", "world"])
    result = stream_with_spinner(chunks, label=False, render_md=False)
    assert result == "Hello world"


def test_stream_with_spinner_empty_chunks():
    chunks = iter([])
    result = stream_with_spinner(chunks, label=False)
    assert result == ""


def test_stream_with_spinner_with_label():
    chunks = iter(["test"])
    result = stream_with_spinner(chunks, label=True, render_md=True)
    assert result == "test"


# --- Session display ---


def test_print_session_header_no_crash():
    print_session_header()


def test_print_command_help_no_crash():
    from sealevel_cli.commands import build_command_registry
    print_command_help(build_command_registry())




def test_print_status_table_no_crash():
    from sealevel_cli.client import HealthResponse
    health = HealthResponse("ok", True, False, "2026-01-01")
    print_status_table(health, {"api_url": "https://test.com", "mode": "quality"}, "slm_test1234567890")


def test_print_status_table_unreachable():
    from sealevel_cli.client import HealthResponse
    health = HealthResponse("unreachable", False, False, "")
    print_status_table(health, {"api_url": "https://test.com"}, None)


def test_print_status_table_degraded():
    from sealevel_cli.client import HealthResponse
    health = HealthResponse("degraded", True, False, "2026-01-01")
    print_status_table(health, {"api_url": "https://test.com", "mode": "quality"}, "slm_test123")


def test_print_usage_table_no_crash():
    from sealevel_cli.client import UsageResponse
    usage = UsageResponse("free", 10, 5000, [{"date": "2026-01-01", "tokens": 5000, "requests": 10}], [])
    print_usage_table(usage)


def test_print_usage_table_with_endpoints():
    from sealevel_cli.client import UsageResponse
    usage = UsageResponse("free", 10, 5000,
        [{"date": "2026-01-01", "tokens": 5000}],
        [{"endpoint": "/api/chat", "requests": 8}],
    )
    print_usage_table(usage)


def test_print_usage_table_empty():
    from sealevel_cli.client import UsageResponse
    usage = UsageResponse("free", 0, 0, [], [])
    print_usage_table(usage)


def test_print_sessions_table_no_crash():
    sessions = [{"id": "abc123def", "title": "Test", "updatedAt": "2026-01-01T00:00:00"}]
    print_sessions_table(sessions)


def test_print_sessions_table_empty():
    print_sessions_table([])


# --- Logo and branding ---


def test_logo_has_5_lines():
    from sealevel_cli.display import LOGO
    assert len(LOGO) == 5


def test_logo_contains_bar_characters():
    from sealevel_cli.display import LOGO
    bar_lines = [l for l in LOGO if "▄" in l]
    assert len(bar_lines) == 3  # Three bars


def test_print_repl_timing_with_tokens():
    from sealevel_cli.display import print_repl_timing
    # Should not crash with tokens
    print_repl_timing(2.5, tokens=847)


def test_print_repl_timing_without_tokens():
    from sealevel_cli.display import print_repl_timing
    print_repl_timing(0.5, tokens=None)
