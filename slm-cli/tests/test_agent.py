"""Tests for sealevel_cli.agent — agent loop with native tool calling."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sealevel_cli.agent import AgentLoop, AGENT_TOOL_PROMPT, AGENT_TOOLS, _call_agent_llm
from sealevel_cli.tools import ToolResult
from sealevel_cli.permissions import PermissionPolicy


# --- Config ---


def test_agent_tools_defined():
    assert len(AGENT_TOOLS) == 6
    names = {t["function"]["name"] for t in AGENT_TOOLS}
    assert names == {"read_file", "write_file", "edit_file", "run_command", "glob_files", "grep_files"}


def test_agent_tool_prompt_has_format_instructions():
    assert "JSON" in AGENT_TOOL_PROMPT or "tool" in AGENT_TOOL_PROMPT.lower()
    assert "edit_file" in AGENT_TOOL_PROMPT or "edit" in AGENT_TOOL_PROMPT.lower()


def test_agent_tool_prompt_has_rules():
    assert "ALWAYS" in AGENT_TOOL_PROMPT or "Never just print" in AGENT_TOOL_PROMPT or "tool" in AGENT_TOOL_PROMPT.lower()


# --- Helpers ---


def _make_session(tmp_path):
    session = MagicMock()
    session.client = MagicMock()
    session.client.last_usage = {"total_tokens": 100}
    session.client.last_finish_reason = "stop"
    session.history = []
    session.turns = 0
    session.total_tokens = 0
    session._capture_tokens.return_value = 100
    session._save_file_checkpoint = MagicMock()
    return session


def _make_response(content="", tool_calls=None, finish_reason="stop"):
    """Build a mock agent LLM response."""
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"
    return {
        "choices": [{"message": message, "finish_reason": finish_reason}],
        "usage": {"total_tokens": 100},
    }


def _make_tool_call(name, args, tc_id="call_1"):
    return {
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
        "id": tc_id,
    }


# --- Agent loop tests ---


def test_agent_loop_no_tool_calls(tmp_path):
    """Plain text response → no tools called."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent._call_agent_llm", return_value=_make_response("A PDA is a Program Derived Address.")):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("What is a PDA?", session)

    assert len(session.history) == 2
    assert "PDA" in session.history[1]["content"]


def test_agent_loop_single_tool_call(tmp_path):
    """read_file → execute → final response."""
    session = _make_session(tmp_path)
    (tmp_path / "lib.rs").write_text("fn main() {}")

    responses = [
        _make_response(tool_calls=[_make_tool_call("read_file", {"path": "lib.rs"})]),
        _make_response("The file contains a main function."),
    ]

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=responses):
        loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
        loop.run("Read lib.rs", session)

    assert len(session.history) == 2
    assert "main function" in session.history[1]["content"]


def test_agent_loop_multi_step(tmp_path):
    """read → edit → final response."""
    session = _make_session(tmp_path)
    (tmp_path / "lib.rs").write_text("fn main() {\n    let x = 1;\n}")

    responses = [
        _make_response(tool_calls=[_make_tool_call("read_file", {"path": "lib.rs"}, "c1")]),
        _make_response(tool_calls=[_make_tool_call("edit_file", {
            "path": "lib.rs", "old_text": "let x = 1;", "new_text": "let x = 42;",
        }, "c2")]),
        _make_response("Done. Changed x to 42."),
    ]

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=responses):
        with patch("sealevel_cli.agent.prompt_permission", return_value="y"):
            loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
            loop.run("Change x to 42", session)

    assert (tmp_path / "lib.rs").read_text().count("let x = 42;") == 1
    assert "Done" in session.history[1]["content"]


def test_agent_loop_permission_denied(tmp_path):
    """Write denied → error sent back to model."""
    session = _make_session(tmp_path)

    responses = [
        _make_response(tool_calls=[_make_tool_call("write_file", {"path": "evil.rs", "content": "bad"})]),
        _make_response("Could not write file."),
    ]

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=responses):
        with patch("sealevel_cli.agent.prompt_permission", return_value="n"):
            loop = AgentLoop(cwd=tmp_path)
            loop.run("Write file", session)

    assert not (tmp_path / "evil.rs").exists()


def test_agent_loop_approve_all(tmp_path):
    """'a' auto-approves subsequent writes."""
    session = _make_session(tmp_path)

    responses = [
        _make_response(tool_calls=[_make_tool_call("write_file", {"path": "a.rs", "content": "// a"}, "c1")]),
        _make_response(tool_calls=[_make_tool_call("write_file", {"path": "b.rs", "content": "// b"}, "c2")]),
        _make_response("Created both."),
    ]

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=responses):
        with patch("sealevel_cli.agent.prompt_permission", return_value="a") as mock_perm:
            loop = AgentLoop(cwd=tmp_path)
            loop.run("Create files", session)

    assert (tmp_path / "a.rs").exists()
    assert (tmp_path / "b.rs").exists()
    assert mock_perm.call_count == 1  # Only prompted once


def test_agent_loop_max_iterations(tmp_path):
    """Loop stops at MAX_ITERATIONS."""
    session = _make_session(tmp_path)
    (tmp_path / "lib.rs").write_text("code")

    response = _make_response(tool_calls=[_make_tool_call("read_file", {"path": "lib.rs"})])

    with patch("sealevel_cli.agent._call_agent_llm", return_value=response):
        loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
        loop.MAX_ITERATIONS = 3
        loop.run("Loop forever", session)

    assert len(session.history) == 2


def test_agent_loop_keyboard_interrupt(tmp_path):
    """Ctrl+C should not crash."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=KeyboardInterrupt):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    assert session.history == [] or len(session.history) == 2


def test_agent_loop_api_error(tmp_path):
    """LLM error should not crash."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=RuntimeError("offline")):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    # Should not crash


def test_agent_loop_edit_prevalidation(tmp_path):
    """edit_file with wrong old_text should fail before asking permission."""
    session = _make_session(tmp_path)
    (tmp_path / "lib.rs").write_text("fn main() {}")

    responses = [
        _make_response(tool_calls=[_make_tool_call("edit_file", {
            "path": "lib.rs", "old_text": "nonexistent text", "new_text": "new",
        })]),
        _make_response("Edit failed."),
    ]

    with patch("sealevel_cli.agent._call_agent_llm", side_effect=responses):
        loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True, auto_writes=True))
        loop.run("Edit lib.rs", session)

    # File unchanged
    assert (tmp_path / "lib.rs").read_text() == "fn main() {}"


def test_agent_loop_empty_response(tmp_path):
    """Empty model response should not crash."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent._call_agent_llm", return_value=_make_response("")):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    assert len(session.history) == 2


# --- Display functions ---


def test_print_tool_call_no_crash():
    from sealevel_cli.agent import _print_tool_call
    _print_tool_call("read_file", {"path": "lib.rs"}, needs_approval=False)
    _print_tool_call("edit_file", {"path": "lib.rs", "old_text": "old", "new_text": "new"}, needs_approval=True)
    _print_tool_call("write_file", {"path": "out.rs", "content": "x" * 100}, needs_approval=True)
    _print_tool_call("run_command", {"command": "anchor build"}, needs_approval=True)


def test_print_tool_result_no_crash():
    from sealevel_cli.agent import _print_tool_result
    _print_tool_result("read_file", ToolResult(True, "File: lib.rs (10 lines)"))
    _print_tool_result("write_file", ToolResult(False, "Permission denied"))


def test_prompt_permission_yes():
    from sealevel_cli.agent import prompt_permission
    with patch("builtins.input", return_value="y"):
        assert prompt_permission("write_file", {"path": "lib.rs"}) == "y"


def test_prompt_permission_no():
    from sealevel_cli.agent import prompt_permission
    with patch("builtins.input", return_value="n"):
        assert prompt_permission("run_command", {"command": "ls"}) == "n"


def test_prompt_permission_keyboard_interrupt():
    from sealevel_cli.agent import prompt_permission
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        assert prompt_permission("write_file", {"path": "x.rs"}) == "n"


def test_project_tree(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")

    loop = AgentLoop(cwd=tmp_path)
    tree = loop._get_project_tree()
    assert "src/lib.rs" in tree
    assert ".git" not in tree
