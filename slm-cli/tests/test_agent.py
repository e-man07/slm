"""Tests for sealevel_cli.agent — agent loop orchestrator."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from sealevel_cli.agent import AgentLoop, AGENT_TOOL_PROMPT, format_tool_results
from sealevel_cli.tool_parser import ToolCall
from sealevel_cli.tools import ToolResult
from sealevel_cli.permissions import PermissionPolicy


# --- AGENT_TOOL_PROMPT ---


def test_agent_tool_prompt_has_tool_names():
    for name in ["read_file", "write_file", "edit_file", "run_command", "glob_files", "grep_files"]:
        assert name in AGENT_TOOL_PROMPT


def test_agent_tool_prompt_has_format_instructions():
    assert "<tool_call>" in AGENT_TOOL_PROMPT
    assert "</tool_call>" in AGENT_TOOL_PROMPT


def test_agent_tool_prompt_has_example():
    assert "read_file" in AGENT_TOOL_PROMPT
    assert "Example" in AGENT_TOOL_PROMPT or "example" in AGENT_TOOL_PROMPT


# --- format_tool_results ---


def test_format_tool_results_success():
    calls = [ToolCall("read_file", {"path": "lib.rs"})]
    results = [ToolResult(True, "fn main() {}")]
    text = format_tool_results(calls, results)
    assert "<tool_result" in text
    assert "read_file" in text
    assert "fn main()" in text
    assert "success" in text


def test_format_tool_results_error():
    calls = [ToolCall("read_file", {"path": "missing.rs"})]
    results = [ToolResult(False, "File not found")]
    text = format_tool_results(calls, results)
    assert "error" in text.lower() or "failed" in text.lower()
    assert "File not found" in text


def test_format_tool_results_multiple():
    calls = [
        ToolCall("read_file", {"path": "a.rs"}),
        ToolCall("read_file", {"path": "b.rs"}),
    ]
    results = [
        ToolResult(True, "content a"),
        ToolResult(True, "content b"),
    ]
    text = format_tool_results(calls, results)
    assert "content a" in text
    assert "content b" in text


# --- AgentLoop ---


def _make_session(tmp_path):
    """Create a mock session for agent tests."""
    session = MagicMock()
    session.client = MagicMock()
    session.client.last_usage = {"total_tokens": 100}
    session.client.last_finish_reason = "stop"
    session.history = []
    session.turns = 0
    session.total_tokens = 0
    session._capture_tokens.return_value = 100
    return session


def test_agent_loop_no_tool_calls(tmp_path):
    """Plain text response → no tools called, response returned."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent.stream_with_spinner", return_value="A PDA is a Program Derived Address."):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("What is a PDA?", session)

    # Should add to session history
    assert len(session.history) == 2
    assert session.history[0]["role"] == "user"
    assert session.history[1]["role"] == "assistant"
    assert "PDA" in session.history[1]["content"]


def test_agent_loop_single_tool_call(tmp_path):
    """Response with tool call → execute → final response."""
    session = _make_session(tmp_path)

    # Create file for read_file tool
    (tmp_path / "lib.rs").write_text("fn main() {}")

    responses = [
        # First response: tool call
        'I\'ll read the file.\n<tool_call>{"name": "read_file", "arguments": {"path": "lib.rs"}}</tool_call>',
        # Second response: final answer (no tool call)
        "The file contains a main function.",
    ]
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
        loop.run("Read lib.rs", session)

    assert call_count == 2
    assert len(session.history) == 2
    assert "main function" in session.history[1]["content"]


def test_agent_loop_permission_denied(tmp_path):
    """Write tool denied → error sent back to model."""
    session = _make_session(tmp_path)

    responses = [
        '<tool_call>{"name": "write_file", "arguments": {"path": "out.rs", "content": "code"}}</tool_call>',
        "I was unable to write the file.",
    ]
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        with patch("sealevel_cli.agent.prompt_permission", return_value="n"):
            loop = AgentLoop(cwd=tmp_path)
            loop.run("Write a file", session)

    assert call_count == 2  # Model got error and responded


def test_agent_loop_max_iterations(tmp_path):
    """Loop stops after MAX_ITERATIONS."""
    session = _make_session(tmp_path)

    (tmp_path / "lib.rs").write_text("code")

    # Always return a tool call — loop should stop at max
    def mock_stream(*args, **kwargs):
        return '<tool_call>{"name": "read_file", "arguments": {"path": "lib.rs"}}</tool_call>'

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
        loop.MAX_ITERATIONS = 3  # Low limit for testing
        loop.run("Read forever", session)

    # Should have stopped after 3 iterations
    assert len(session.history) == 2  # user + final assistant


def test_agent_loop_keyboard_interrupt(tmp_path):
    """Ctrl+C during agent loop should not crash, history stays empty."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=KeyboardInterrupt):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    assert session.history == []  # Nothing persisted on interrupt


def test_agent_loop_api_error(tmp_path):
    """API error during agent loop should not crash, history stays empty."""
    from sealevel_cli.client import SealevelError
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=SealevelError("offline")):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    assert session.history == []  # Nothing persisted on error


def test_agent_loop_permission_prompt_called(tmp_path):
    """Permission prompt should be called for write tools."""
    session = _make_session(tmp_path)

    responses = [
        '<tool_call>{"name": "write_file", "arguments": {"path": "out.rs", "content": "x"}}</tool_call>',
        "Done.",
    ]
    call_count = 0
    def mock_stream(*args, **kwargs):
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        with patch("sealevel_cli.agent.prompt_permission", return_value="y") as mock_prompt:
            loop = AgentLoop(cwd=tmp_path)
            loop.run("write file", session)
            mock_prompt.assert_called_once()
            assert mock_prompt.call_args[0][0] == "write_file"


def test_agent_loop_approve_all_persists(tmp_path):
    """'a' (approve all) should auto-approve subsequent write tools."""
    session = _make_session(tmp_path)

    responses = [
        '<tool_call>{"name": "write_file", "arguments": {"path": "a.rs", "content": "a"}}</tool_call>',
        '<tool_call>{"name": "write_file", "arguments": {"path": "b.rs", "content": "b"}}</tool_call>',
        "Done.",
    ]
    call_count = 0
    def mock_stream(*args, **kwargs):
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        with patch("sealevel_cli.agent.prompt_permission", return_value="a") as mock_prompt:
            loop = AgentLoop(cwd=tmp_path)
            loop.run("write files", session)
            # First call prompts, second should be auto-approved (policy mutated)
            assert mock_prompt.call_count == 1  # Only prompted once


def test_agent_loop_empty_response(tmp_path):
    """Empty model response should not crash."""
    session = _make_session(tmp_path)

    with patch("sealevel_cli.agent.stream_with_spinner", return_value=""):
        loop = AgentLoop(cwd=tmp_path)
        loop.run("test", session)

    assert len(session.history) == 2
    assert session.history[1]["content"] == ""


def test_agent_loop_tool_executor_crash(tmp_path):
    """If tool executor raises unexpected exception, agent loop should not crash."""
    session = _make_session(tmp_path)

    responses = [
        '<tool_call>{"name": "read_file", "arguments": {"path": "crash.rs"}}</tool_call>',
        "Error noted.",
    ]
    call_count = 0
    def mock_stream(*args, **kwargs):
        nonlocal call_count
        r = responses[call_count]
        call_count += 1
        return r

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        with patch("sealevel_cli.agent.execute_tool", side_effect=RuntimeError("unexpected crash")):
            loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
            loop.run("read crash.rs", session)

    assert call_count == 2  # Error sent back, model responded


def test_agent_loop_multi_step(tmp_path):
    """Multiple tool calls across iterations."""
    session = _make_session(tmp_path)
    (tmp_path / "lib.rs").write_text("old code")

    responses = [
        '<tool_call>{"name": "read_file", "arguments": {"path": "lib.rs"}}</tool_call>',
        '<tool_call>{"name": "edit_file", "arguments": {"path": "lib.rs", "old_text": "old code", "new_text": "new code"}}</tool_call>',
        "Done. File updated.",
    ]
    call_count = 0

    def mock_stream(*args, **kwargs):
        nonlocal call_count
        result = responses[call_count]
        call_count += 1
        return result

    with patch("sealevel_cli.agent.stream_with_spinner", side_effect=mock_stream):
        with patch("sealevel_cli.agent.prompt_permission", return_value="y"):
            loop = AgentLoop(cwd=tmp_path, policy=PermissionPolicy(auto_reads=True))
            loop.run("Update lib.rs", session)

    assert call_count == 3
    assert (tmp_path / "lib.rs").read_text() == "new code"
    assert "updated" in session.history[1]["content"].lower()
