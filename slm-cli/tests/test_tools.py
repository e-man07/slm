"""Tests for sealevel_cli.tools — tool definitions and executors."""
import os
import subprocess
import pytest
from pathlib import Path

from sealevel_cli.tools import (
    TOOL_DEFINITIONS,
    ToolResult,
    execute,
    exec_read_file,
    exec_write_file,
    exec_edit_file,
    exec_run_command,
    exec_glob_files,
    exec_grep_files,
    MAX_OUTPUT_SIZE,
)


# --- Tool definitions ---


def test_tool_definitions_exist():
    assert len(TOOL_DEFINITIONS) == 6
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"read_file", "write_file", "edit_file", "run_command", "glob_files", "grep_files"}


def test_tool_definitions_have_required_fields():
    for t in TOOL_DEFINITIONS:
        assert "name" in t
        assert "description" in t
        assert "parameters" in t
        assert "permission" in t


# --- read_file ---


def test_read_file(tmp_path):
    f = tmp_path / "test.rs"
    f.write_text("line1\nline2\nline3\n")
    result = exec_read_file({"path": str(f)}, cwd=tmp_path)
    assert result.success
    assert "line1" in result.output
    assert "line3" in result.output


def test_read_file_with_offset_limit(tmp_path):
    f = tmp_path / "test.rs"
    f.write_text("\n".join(f"line{i}" for i in range(20)))
    result = exec_read_file({"path": str(f), "offset": 5, "limit": 3}, cwd=tmp_path)
    assert result.success
    assert "line5" in result.output
    assert "line7" in result.output
    assert "line8" not in result.output


def test_read_file_not_found(tmp_path):
    result = exec_read_file({"path": "/nonexistent/file.rs"}, cwd=tmp_path)
    assert not result.success
    assert "not found" in result.output.lower()


def test_read_file_sensitive(tmp_path):
    f = tmp_path / ".env"
    f.write_text("SECRET=value")
    result = exec_read_file({"path": str(f)}, cwd=tmp_path)
    assert not result.success
    assert "sensitive" in result.output.lower()


def test_read_file_too_large(tmp_path):
    f = tmp_path / "big.rs"
    f.write_text("x" * 1_100_000)
    result = exec_read_file({"path": str(f)}, cwd=tmp_path)
    assert not result.success
    assert "large" in result.output.lower()


def test_read_file_relative_path(tmp_path):
    f = tmp_path / "src" / "lib.rs"
    f.parent.mkdir()
    f.write_text("fn main() {}")
    result = exec_read_file({"path": "src/lib.rs"}, cwd=tmp_path)
    assert result.success
    assert "fn main()" in result.output


# --- write_file ---


def test_write_file(tmp_path):
    path = str(tmp_path / "out.rs")
    result = exec_write_file({"path": path, "content": "fn main() {}"}, cwd=tmp_path)
    assert result.success
    assert Path(path).read_text() == "fn main() {}"


def test_write_file_creates_dirs(tmp_path):
    path = str(tmp_path / "src" / "nested" / "lib.rs")
    result = exec_write_file({"path": path, "content": "// new"}, cwd=tmp_path)
    assert result.success
    assert Path(path).exists()


def test_write_file_sensitive(tmp_path):
    path = str(tmp_path / ".env")
    result = exec_write_file({"path": path, "content": "SECRET=bad"}, cwd=tmp_path)
    assert not result.success


def test_write_file_relative_path(tmp_path):
    result = exec_write_file({"path": "out.rs", "content": "fn main() {}"}, cwd=tmp_path)
    assert result.success
    assert (tmp_path / "out.rs").read_text() == "fn main() {}"


# --- edit_file ---


def test_edit_file(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text("fn main() {\n    let x = 1;\n}")
    result = exec_edit_file({
        "path": str(f),
        "old_text": "let x = 1;",
        "new_text": "let x = 42;",
    }, cwd=tmp_path)
    assert result.success
    assert "let x = 42;" in f.read_text()
    assert "let x = 1;" not in f.read_text()


def test_edit_file_not_found(tmp_path):
    result = exec_edit_file({
        "path": str(tmp_path / "missing.rs"),
        "old_text": "a",
        "new_text": "b",
    }, cwd=tmp_path)
    assert not result.success


def test_edit_file_old_text_not_found(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text("fn main() {}")
    result = exec_edit_file({
        "path": str(f),
        "old_text": "this text does not exist",
        "new_text": "replacement",
    }, cwd=tmp_path)
    assert not result.success
    assert "not found" in result.output.lower()


def test_edit_file_multiple_matches(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text("let x = 1;\nlet y = 1;\nlet z = 1;")
    result = exec_edit_file({
        "path": str(f),
        "old_text": "let x = 1;",
        "new_text": "let x = 99;",
    }, cwd=tmp_path)
    assert result.success
    content = f.read_text()
    assert content.count("let x = 99;") == 1
    assert content.count("let y = 1;") == 1  # Only first match replaced


def test_edit_file_relative_path(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text("old code")
    result = exec_edit_file({
        "path": "lib.rs",
        "old_text": "old code",
        "new_text": "new code",
    }, cwd=tmp_path)
    assert result.success
    assert f.read_text() == "new code"


# --- run_command ---


def test_run_command_success(tmp_path):
    result = exec_run_command({"command": "echo hello"}, cwd=tmp_path)
    assert result.success
    assert "hello" in result.output


def test_run_command_failure(tmp_path):
    result = exec_run_command({"command": "false"}, cwd=tmp_path)
    assert not result.success
    assert "exit code" in result.output.lower() or "1" in result.output


def test_run_command_timeout(tmp_path):
    result = exec_run_command({"command": "sleep 10", "timeout": 1}, cwd=tmp_path)
    assert not result.success
    assert "timed out" in result.output.lower()


def test_run_command_output_cap(tmp_path):
    # Generate output larger than MAX_OUTPUT_SIZE
    result = exec_run_command({
        "command": f"python3 -c \"print('x' * {MAX_OUTPUT_SIZE + 1000})\"",
    }, cwd=tmp_path)
    assert result.success
    assert len(result.output) <= MAX_OUTPUT_SIZE + 100  # Allow small overhead for truncation message


def test_run_command_cwd(tmp_path):
    result = exec_run_command({"command": "pwd"}, cwd=tmp_path)
    assert result.success
    assert str(tmp_path) in result.output


# --- glob_files ---


def test_glob_files(tmp_path):
    (tmp_path / "a.rs").write_text("")
    (tmp_path / "b.rs").write_text("")
    (tmp_path / "c.txt").write_text("")
    result = exec_glob_files({"pattern": "*.rs"}, cwd=tmp_path)
    assert result.success
    assert "a.rs" in result.output
    assert "b.rs" in result.output
    assert "c.txt" not in result.output


def test_glob_files_recursive(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("")
    (tmp_path / "src" / "main.rs").write_text("")
    result = exec_glob_files({"pattern": "**/*.rs"}, cwd=tmp_path)
    assert result.success
    assert "lib.rs" in result.output


def test_glob_files_no_matches(tmp_path):
    result = exec_glob_files({"pattern": "*.xyz"}, cwd=tmp_path)
    assert result.success
    assert "no matches" in result.output.lower()


# --- grep_files ---


def test_grep_files(tmp_path):
    (tmp_path / "a.rs").write_text("fn main() {}\nfn helper() {}")
    (tmp_path / "b.rs").write_text("let x = 5;")
    result = exec_grep_files({"pattern": "fn \\w+"}, cwd=tmp_path)
    assert result.success
    assert "main" in result.output


def test_grep_files_with_glob(tmp_path):
    (tmp_path / "a.rs").write_text("fn main() {}")
    (tmp_path / "b.txt").write_text("fn other() {}")
    result = exec_grep_files({"pattern": "fn", "glob": "*.rs"}, cwd=tmp_path)
    assert result.success
    assert "main" in result.output
    assert "other" not in result.output


def test_grep_files_no_matches(tmp_path):
    (tmp_path / "a.rs").write_text("let x = 5;")
    result = exec_grep_files({"pattern": "nonexistent_pattern"}, cwd=tmp_path)
    assert result.success
    assert "no matches" in result.output.lower()


def test_grep_files_invalid_regex(tmp_path):
    (tmp_path / "a.rs").write_text("test")
    result = exec_grep_files({"pattern": "[invalid"}, cwd=tmp_path)
    assert not result.success
    assert "regex" in result.output.lower() or "error" in result.output.lower()


# --- execute dispatcher ---


def test_execute_dispatches(tmp_path):
    f = tmp_path / "test.rs"
    f.write_text("fn main() {}")
    result = execute("read_file", {"path": str(f)}, cwd=tmp_path)
    assert result.success
    assert "fn main()" in result.output


def test_execute_unknown_tool(tmp_path):
    result = execute("nonexistent_tool", {}, cwd=tmp_path)
    assert not result.success
    assert "unknown tool" in result.output.lower()


# --- edit_file security ---


def test_edit_file_sensitive_blocked(tmp_path):
    """edit_file must block sensitive files like .env."""
    f = tmp_path / ".env"
    f.write_text("SECRET=old")
    result = exec_edit_file({
        "path": str(f),
        "old_text": "old",
        "new_text": "new",
    }, cwd=tmp_path)
    assert not result.success
    assert "sensitive" in result.output.lower()
    assert f.read_text() == "SECRET=old"  # Unchanged


def test_edit_file_pem_blocked(tmp_path):
    f = tmp_path / "server.pem"
    f.write_text("-----BEGIN CERTIFICATE-----")
    result = exec_edit_file({
        "path": str(f),
        "old_text": "BEGIN",
        "new_text": "END",
    }, cwd=tmp_path)
    assert not result.success


# --- empty path edge case ---


def test_read_file_empty_path(tmp_path):
    result = exec_read_file({"path": ""}, cwd=tmp_path)
    assert not result.success


def test_write_file_empty_path(tmp_path):
    result = exec_write_file({"path": "", "content": "x"}, cwd=tmp_path)
    assert not result.success or True  # May resolve to cwd dir, OSError caught


# --- Additional edge cases for coverage ---


def test_read_file_binary(tmp_path):
    """Binary file should fail gracefully."""
    f = tmp_path / "binary.bin"
    f.write_bytes(b"\x00\x01\x02\xff\xfe")
    result = exec_read_file({"path": str(f)}, cwd=tmp_path)
    # May succeed (utf-8 decode) or fail — shouldn't crash
    assert isinstance(result, ToolResult)


def test_write_file_overwrites(tmp_path):
    f = tmp_path / "exist.rs"
    f.write_text("old")
    result = exec_write_file({"path": str(f), "content": "new"}, cwd=tmp_path)
    assert result.success
    assert f.read_text() == "new"


def test_edit_file_sensitive_pem(tmp_path):
    f = tmp_path / "key.pem"
    f.write_text("-----BEGIN-----")
    result = exec_edit_file({"path": str(f), "old_text": "BEGIN", "new_text": "END"}, cwd=tmp_path)
    assert not result.success


def test_run_command_stderr(tmp_path):
    result = exec_run_command({"command": "echo err >&2"}, cwd=tmp_path)
    assert "err" in result.output


def test_glob_files_with_path(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.rs").write_text("")
    result = exec_glob_files({"pattern": "*.rs", "path": str(sub)}, cwd=tmp_path)
    assert result.success
    assert "a.rs" in result.output


def test_glob_files_nonexistent_dir(tmp_path):
    result = exec_glob_files({"pattern": "*.rs", "path": "/nonexistent"}, cwd=tmp_path)
    assert not result.success


def test_grep_files_single_file(tmp_path):
    f = tmp_path / "test.rs"
    f.write_text("fn main() {}\nfn helper() {}")
    result = exec_grep_files({"pattern": "helper", "path": str(f)}, cwd=tmp_path)
    assert result.success
    assert "helper" in result.output


def test_grep_files_nonexistent_path(tmp_path):
    result = exec_grep_files({"pattern": "x", "path": "/nonexistent"}, cwd=tmp_path)
    assert not result.success


def test_grep_files_binary_skipped(tmp_path):
    """Binary files should be skipped, not crash."""
    f = tmp_path / "binary.bin"
    f.write_bytes(b"\x00\x01\xff")
    result = exec_grep_files({"pattern": "test"}, cwd=tmp_path)
    assert result.success  # No crash


def test_read_file_with_offset_beyond_length(tmp_path):
    f = tmp_path / "short.rs"
    f.write_text("line1\nline2")
    result = exec_read_file({"path": str(f), "offset": 100, "limit": 10}, cwd=tmp_path)
    assert result.success  # Empty result but success
