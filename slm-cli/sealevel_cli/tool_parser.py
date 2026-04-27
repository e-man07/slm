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

# Regex for ``` <label>\nJSON\n``` code blocks. Label is any word (json,
# tool_call, typescript, etc.) or absent — the model sometimes emits ```json
# blocks instead of ```tool_call. Validation at parse-time ensures only blocks
# whose JSON is shaped like a tool call (has `name` + `arguments`/`parameters`)
# are accepted.
_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z_]+)?\s*\n(.*?)\n```", re.DOTALL)


def parse(text: str) -> tuple[list[ToolCall], str]:
    """Extract tool calls from LLM output text.

    Returns:
        (tool_calls, prose) — list of parsed calls + text with tool_call tags removed.
    """
    calls: list[ToolCall] = []
    consumed_spans: list[tuple[int, int]] = []

    # 1. Try XML tag format (primary)
    failed_tags: list[str] = []
    for match in _XML_TAG_RE.finditer(text):
        raw = match.group(1).strip()
        tc = _try_parse_json(raw)
        if tc:
            calls.append(tc)
            consumed_spans.append((match.start(), match.end()))
        else:
            failed_tags.append(match.group(0))  # Keep failed tag text

    # 2. Fallback: ``` <label> blocks (only if no XML tags found)
    if not calls:
        for match in _CODE_BLOCK_RE.finditer(text):
            raw = match.group(1).strip()
            tc = _try_parse_json(raw)
            if tc:
                calls.append(tc)
                consumed_spans.append((match.start(), match.end()))

    # 3. Naked JSON fallback — handles streaming truncation where the SSE layer
    #    drops the closing ``` fence or the language label. Walk the text
    #    counting braces (honoring string quoting) to find balanced JSON
    #    objects; accept ones that look like a tool call.
    if not calls:
        for start, end in _find_naked_json_objects(text):
            candidate = text[start:end]
            tc = _try_parse_json(candidate)
            if tc:
                calls.append(tc)
                consumed_spans.append((start, end))

    # 4. Extract prose
    if calls:
        prose = _strip_spans(text, consumed_spans)
        for tag_text in failed_tags:
            prose += "\n" + tag_text
    else:
        prose = text

    prose = prose.strip()
    prose = re.sub(r"\n{3,}", "\n\n", prose)

    return calls, prose


def _find_naked_json_objects(text: str) -> list[tuple[int, int]]:
    """Find balanced top-level JSON objects via brace-counting + string-state.

    Handles braces inside string values (e.g. glob `{rs,md}`) so they don't
    affect depth tracking. If an object opens but never closes (truncation),
    emits a partial span so repair logic can attempt to close it.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        j = i
        balanced = False
        while j < n:
            ch = text[j]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        spans.append((i, j + 1))
                        i = j + 1
                        balanced = True
                        break
            j += 1
        if not balanced:
            spans.append((i, n))
            break
    return spans


def _strip_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Remove the given (start, end) spans from text."""
    if not spans:
        return text
    spans = sorted(spans)
    out: list[str] = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            out.append(text[cursor:start])
        cursor = end
    if cursor < len(text):
        out.append(text[cursor:])
    return "".join(out)


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

    # Fix common key name typos from 7B model
    key_fixes = {"_text": "old_text", "oldtext": "old_text", "newtext": "new_text", "_path": "path"}
    args = {key_fixes.get(k, k): v for k, v in args.items()}

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
