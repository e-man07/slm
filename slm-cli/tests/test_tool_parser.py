"""Tests for sealevel_cli.tool_parser — parse tool calls from LLM text output."""
import pytest

from sealevel_cli.tool_parser import ToolCall, parse


# --- XML tag format ---


def test_parse_single_tool_call():
    text = 'I\'ll read the file.\n<tool_call>{"name": "read_file", "arguments": {"path": "src/lib.rs"}}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].args == {"path": "src/lib.rs"}
    assert "I'll read the file." in prose
    assert "<tool_call>" not in prose


def test_parse_multiple_tool_calls():
    text = (
        'Let me check both files.\n'
        '<tool_call>{"name": "read_file", "arguments": {"path": "a.rs"}}</tool_call>\n'
        '<tool_call>{"name": "read_file", "arguments": {"path": "b.rs"}}</tool_call>'
    )
    calls, prose = parse(text)
    assert len(calls) == 2
    assert calls[0].args["path"] == "a.rs"
    assert calls[1].args["path"] == "b.rs"
    assert "check both files" in prose


def test_parse_tool_call_with_complex_args():
    text = '<tool_call>{"name": "edit_file", "arguments": {"path": "lib.rs", "old_text": "fn main() {}", "new_text": "fn main() {\\n    println!(\\\"hello\\\");\\n}"}}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "edit_file"
    assert "old_text" in calls[0].args
    assert "new_text" in calls[0].args


def test_parse_no_tool_calls():
    text = "A PDA is a Program Derived Address used in Solana."
    calls, prose = parse(text)
    assert len(calls) == 0
    assert prose == text


def test_parse_empty_text():
    calls, prose = parse("")
    assert len(calls) == 0
    assert prose == ""


def test_parse_prose_before_and_after_tool_call():
    text = "First, I'll read.\n<tool_call>{\"name\": \"read_file\", \"arguments\": {\"path\": \"x.rs\"}}</tool_call>\nDone reading."
    calls, prose = parse(text)
    assert len(calls) == 1
    assert "First, I'll read." in prose
    assert "Done reading." in prose


def test_parse_tool_call_multiline_json():
    text = '<tool_call>\n{\n  "name": "write_file",\n  "arguments": {\n    "path": "out.rs",\n    "content": "fn main() {}"\n  }\n}\n</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "write_file"
    assert calls[0].args["content"] == "fn main() {}"


# --- Code block fallback ---


def test_parse_code_block_format():
    text = 'Reading file.\n```tool_call\n{"name": "read_file", "arguments": {"path": "lib.rs"}}\n```'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_parse_code_block_with_json_label():
    text = '```json\n{"name": "glob_files", "arguments": {"pattern": "**/*.rs"}}\n```'
    # Upstream parser accepts any code block label if JSON is tool-shaped
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "glob_files"


# --- JSON repair ---


def test_parse_missing_closing_brace():
    text = '<tool_call>{"name": "read_file", "arguments": {"path": "lib.rs"}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_parse_single_quotes():
    text = "<tool_call>{'name': 'read_file', 'arguments': {'path': 'lib.rs'}}</tool_call>"
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_parse_trailing_comma():
    text = '<tool_call>{"name": "read_file", "arguments": {"path": "lib.rs",}}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_parse_completely_malformed_json():
    """Totally broken JSON should be skipped, not crash."""
    text = "<tool_call>this is not json at all</tool_call>"
    calls, prose = parse(text)
    assert len(calls) == 0
    # Original text preserved in prose
    assert "not json" in prose


# --- Edge cases ---


def test_parse_unknown_tool_name():
    """Unknown tool names should still be parsed — validation happens at execution."""
    text = '<tool_call>{"name": "unknown_tool", "arguments": {}}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "unknown_tool"


def test_parse_arguments_key_variants():
    """Model might use 'parameters' instead of 'arguments'."""
    text = '<tool_call>{"name": "read_file", "parameters": {"path": "lib.rs"}}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].args == {"path": "lib.rs"}


def test_parse_extra_whitespace():
    text = '  <tool_call>  {"name": "read_file", "arguments": {"path": "lib.rs"}}  </tool_call>  '
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"


def test_parse_tool_call_no_arguments():
    text = '<tool_call>{"name": "read_file"}</tool_call>'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].args == {}


def test_parse_nested_tool_call_tags_in_prose():
    """Model might mention <tool_call> in explanation text — should not parse."""
    text = "To call a tool, use <tool_call> tags. Here is an example."
    calls, prose = parse(text)
    assert len(calls) == 0  # No valid JSON between tags


def test_parse_rust_code_not_confused_with_tool_call():
    """Rust code blocks should not be confused with tool calls."""
    text = "```rust\nfn main() {\n    let x = 5;\n}\n```"
    calls, prose = parse(text)
    assert len(calls) == 0


def test_parse_preserves_prose_order():
    text = "Step 1.\n<tool_call>{\"name\": \"read_file\", \"arguments\": {\"path\": \"a.rs\"}}</tool_call>\nStep 2.\n<tool_call>{\"name\": \"read_file\", \"arguments\": {\"path\": \"b.rs\"}}</tool_call>\nStep 3."
    calls, prose = parse(text)
    assert len(calls) == 2
    assert "Step 1." in prose
    assert "Step 2." in prose
    assert "Step 3." in prose


# --- Bare JSON format (no wrapper tags) ---


def test_parse_bare_json_tool_call():
    """Model outputs JSON without <tool_call> tags."""
    text = 'I\'ll read the file.\n{"name": "read_file", "arguments": {"path": "src/lib.rs"}}'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "read_file"
    assert calls[0].args["path"] == "src/lib.rs"
    assert "I'll read the file." in prose


def test_parse_bare_json_accepts_any_tool_name():
    """Upstream parser accepts any tool-shaped JSON — validation at execution time."""
    text = '{"name": "unknown_thing", "arguments": {"x": 1}}'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "unknown_thing"


def test_parse_bare_json_edit_file():
    text = '{"name": "edit_file", "arguments": {"path": "lib.rs", "old_text": "old", "new_text": "new"}}'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert calls[0].name == "edit_file"


def test_parse_bare_json_with_prose():
    text = 'Let me check.\n{"name": "glob_files", "arguments": {"pattern": "**/*.rs"}}\nDone.'
    calls, prose = parse(text)
    assert len(calls) == 1
    assert "Let me check." in prose


def test_parse_truncated_tool_call():
    """If model output was truncated mid-tool-call, skip it."""
    text = '<tool_call>{"name": "read_file", "arguments": {"path": "lib.'
    calls, prose = parse(text)
    assert len(calls) == 0  # No closing tag = not a valid tool call
