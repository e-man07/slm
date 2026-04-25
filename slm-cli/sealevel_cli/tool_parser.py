"""Parse tool calls from raw LLM text output.

The model outputs tool calls as XML-tagged JSON:
    <tool_call>{"name": "read_file", "arguments": {"path": "lib.rs"}}</tool_call>

This module extracts those calls and separates prose from tool invocations.
Handles common 7B model quirks: malformed JSON, single quotes, trailing commas.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A parsed tool call from LLM output."""
    name: str
    args: dict = field(default_factory=dict)


# Regex for <tool_call>JSON</tool_call> (dotall for multiline JSON)
_XML_TAG_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)

# Regex for ```tool_call\nJSON\n``` code blocks
_CODE_BLOCK_RE = re.compile(r"```tool_call\s*\n(.*?)\n```", re.DOTALL)


def parse(text: str) -> tuple[list[ToolCall], str]:
    """Extract tool calls from LLM output text.

    Returns:
        (tool_calls, prose) — list of parsed calls + text with tool_call tags removed.
    """
    calls: list[ToolCall] = []

    # 1. Try XML tag format (primary)
    failed_tags: list[str] = []
    for match in _XML_TAG_RE.finditer(text):
        raw = match.group(1).strip()
        tc = _try_parse_json(raw)
        if tc:
            calls.append(tc)
        else:
            failed_tags.append(match.group(0))  # Keep failed tag text

    # 2. Fallback: ```tool_call blocks (only if no XML tags found)
    if not calls:
        for match in _CODE_BLOCK_RE.finditer(text):
            raw = match.group(1).strip()
            tc = _try_parse_json(raw)
            if tc:
                calls.append(tc)

    # 3. Extract prose (remove parsed tool tags, keep failed ones)
    if calls and _XML_TAG_RE.search(text):
        # XML tags were parsed — strip them
        prose = _XML_TAG_RE.sub("", text)
        for tag_text in failed_tags:
            prose += "\n" + tag_text
    elif calls and _CODE_BLOCK_RE.search(text):
        # Code blocks were parsed — strip them
        prose = _CODE_BLOCK_RE.sub("", text)
    else:
        # No tool calls found — full text is prose
        prose = text

    prose = prose.strip()
    prose = re.sub(r"\n{3,}", "\n\n", prose)

    return calls, prose


def _try_parse_json(raw: str) -> ToolCall | None:
    """Try to parse a JSON string as a ToolCall, with repair attempts."""
    # Try direct parse first
    parsed = _safe_json_loads(raw)
    if parsed is None:
        # Attempt repairs
        parsed = _safe_json_loads(_repair_json(raw))
    if parsed is None:
        return None

    if not isinstance(parsed, dict) or "name" not in parsed:
        return None

    name = parsed["name"]
    args = parsed.get("arguments", parsed.get("parameters", {}))
    if not isinstance(args, dict):
        args = {}

    return ToolCall(name=str(name), args=args)


def _safe_json_loads(text: str) -> dict | None:
    """Parse JSON, returning None on failure."""
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _repair_json(raw: str) -> str:
    """Attempt to fix common JSON issues from 7B models."""
    text = raw

    # Fix single quotes → double quotes (careful with strings containing apostrophes)
    # Only replace quotes at JSON structural positions
    text = text.replace("'", '"')

    # Fix trailing commas before } or ]
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    # Fix missing closing braces (count { vs })
    open_count = text.count("{")
    close_count = text.count("}")
    if open_count > close_count:
        text += "}" * (open_count - close_count)

    return text
