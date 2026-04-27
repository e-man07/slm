"""V2-only tool call parser — handles both canonical and naked-JSON forms.

This is an EXPERIMENTAL parser used only to test whether the v2 LoRA adapter
produces usable tool calls despite missing the <tool_call> wrapper tags.

DO NOT IMPORT FROM slm-cli/sealevel_cli/. This file lives in scripts/v2_test/
to keep production parser untouched until we've verified the v2 adapter works.

Behavior vs production parser:
  - Canonical <tool_call>{...}</tool_call>      → both parse it
  - ```tool_call ... ``` code block            → both parse it
  - ```typescript / ```json / ```any ... ```   → ONLY v2 parses (with validation)
  - Naked JSON {"name":..., "arguments":...}   → ONLY v2 parses (with validation)

The "validation" step requires the candidate JSON to have:
  - a `name` field that matches a known tool name from TOOL_DEFINITIONS
  - either `arguments` or `parameters` being a dict
This avoids false positives on unrelated JSON.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Use the production tool definitions as canonical source of valid tool names.
# Requires `sealevel` (pip install sealevel) to be available in the env.
from sealevel_cli.tools import TOOL_DEFINITIONS  # type: ignore  # noqa: E402

VALID_TOOL_NAMES = {td["name"] for td in TOOL_DEFINITIONS}


@dataclass
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


# ── Patterns (in priority order) ──

# 1. Canonical: <tool_call>{...}</tool_call>
_XML_RE = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)

# 2. Code block with any label: ```anything {...} ```
#    Captures content INSIDE any fenced block. We later validate it looks like a tool call.
_CODE_BLOCK_RE = re.compile(r"```(?:[a-zA-Z_]+)?\s*\n?(.*?)```", re.DOTALL)

# 3. Naked JSON detection: walk text looking for `{`, count braces to find
#    matching `}`, while honoring quoted strings (so `{rs,md}` inside a string
#    value doesn't break depth tracking). Used by `_find_naked_json_objects`.


def parse(text: str) -> tuple[list[ToolCall], str]:
    """Extract tool calls from LLM output, supporting v2 model's naked-JSON style.

    Returns (tool_calls, prose_with_calls_stripped).
    """
    calls: list[ToolCall] = []
    consumed_spans: list[tuple[int, int]] = []  # for stripping from prose

    # 1. Canonical XML
    for m in _XML_RE.finditer(text):
        tc = _try_parse_tool_call_json(m.group(1).strip())
        if tc:
            calls.append(tc)
            consumed_spans.append((m.start(), m.end()))

    # If we found canonical, prefer that exclusively
    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 2. Code blocks with any label
    for m in _CODE_BLOCK_RE.finditer(text):
        candidate = m.group(1).strip()
        # The content might be JSON, or might be code containing JSON
        tc = _try_parse_tool_call_json(candidate)
        if tc and tc.name in VALID_TOOL_NAMES:
            calls.append(tc)
            consumed_spans.append((m.start(), m.end()))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 3. Naked JSON — brace-counting walk that handles braces inside string values
    for start, end in _find_naked_json_objects(text):
        candidate = text[start:end]
        tc = _try_parse_tool_call_json(candidate)
        if tc and tc.name in VALID_TOOL_NAMES:
            calls.append(tc)
            consumed_spans.append((start, end))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 4. "tool_name {args}" format — model emits the tool name followed by
    #    JSON-only args (no `name` field inside the JSON).
    for tool_name in VALID_TOOL_NAMES:
        # Match: word boundary, tool name, optional space/colon/(/=, then `{`
        pattern = re.compile(
            r"\b" + re.escape(tool_name) + r"\b\s*[:=(]?\s*(\{)",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            brace_pos = m.start(1)
            # Walk to find matching close brace from this point
            partial_spans = _find_naked_json_objects(text[brace_pos:])
            if not partial_spans:
                continue
            s, e = partial_spans[0]
            args_raw = text[brace_pos + s : brace_pos + e]
            args = _safe_json_loads(args_raw) or _safe_json_loads(_repair_json(args_raw))
            if isinstance(args, dict) and args:
                # Skip if args dict happens to itself be a {name, arguments} payload
                # — that should have been caught at step 3.
                if "name" in args and "arguments" in args and isinstance(args.get("arguments"), dict):
                    continue
                calls.append(ToolCall(name=tool_name, args=args))
                consumed_spans.append((m.start(), brace_pos + e))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 4b. Fuzzy intent matching: model emits unknown tool name like
    #     `andbox_read("/path")` or `ElementsByTagNameRequest { query: "..." }`.
    #     Map by keyword in the name + arg shape.
    #     Mirrors Claude's runtime fuzzy-matching when models hallucinate names.
    INTENT_KEYWORDS = [
        # (keyword, tool_name) — checked in order; first match wins
        ("read", "read_file"),
        ("open", "read_file"),  # `andbox_open(path)` / `file_open`
        ("cat", "read_file"),
        ("show", "read_file"),
        ("write", "write_file"),
        ("create", "write_file"),
        ("save", "write_file"),
        ("edit", "edit_file"),
        ("replace", "edit_file"),
        ("update", "edit_file"),
        ("modify", "edit_file"),
        ("glob", "glob_files"),
        ("find", "glob_files"),
        ("list", "glob_files"),
        ("ls", "glob_files"),
        ("grep", "grep_files"),
        ("search", "grep_files"),
        ("query", "grep_files"),
        ("scan", "grep_files"),
        ("run", "run_command"),
        ("exec", "run_command"),
        ("shell", "run_command"),
        ("cmd", "run_command"),
        ("bash", "run_command"),
    ]

    def infer_tool_from_name(name: str) -> str | None:
        n = name.lower()
        for kw, tool in INTENT_KEYWORDS:
            if kw in n:
                return tool
        return None

    def infer_tool_from_args(args: dict) -> str | None:
        """Fallback: when name gives no signal, infer from arg key shape."""
        if not isinstance(args, dict):
            return None
        keys = {k.lower() for k in args.keys()}
        # query + scope/path → grep
        if {"query"} & keys or {"search"} & keys or {"regex"} & keys:
            return "grep_files"
        # command/cmd → run_command
        if {"command", "cmd", "shell"} & keys:
            return "run_command"
        # pattern → glob_files (default; grep handled above by 'query')
        if "pattern" in keys and ("path" in keys or "directory" in keys or "dir" in keys):
            return "glob_files"
        # old_text/new_text → edit_file
        if {"old_text", "new_text"} & keys or {"old", "new"} & keys:
            return "edit_file"
        # content → write_file
        if {"content", "text", "data", "body"} & keys and "path" in keys:
            return "write_file"
        # bare path → read_file
        if "path" in keys and len(keys) == 1:
            return "read_file"
        return None

    def remap_args_for_tool(args: dict, tool: str) -> dict:
        """Map common synonym keys to the tool's expected param names."""
        if not isinstance(args, dict):
            return {}
        synonyms = {
            "query": "pattern",
            "search": "pattern",
            "regex": "pattern",
            "scope": "path",
            "directory": "path",
            "dir": "path",
            "file": "path",
            "filepath": "path",
            "filename": "path",
            "text": "content",
            "data": "content",
            "body": "content",
            "old": "old_text",
            "new": "new_text",
            "from": "old_text",
            "to": "new_text",
            "command": "command",
            "cmd": "command",
            "shell": "command",
        }
        out = {}
        for k, v in args.items():
            new_k = synonyms.get(k.lower(), k)
            # Coerce non-string scope objects to a path string if needed
            if isinstance(v, dict) and "File" in str(v):
                # crude: extract first string
                for vv in v.values():
                    if isinstance(vv, str):
                        v = vv
                        break
            out[new_k] = v
        return out

    # Try unknown-name function calls: `WORD(...)` or `WORD { ... }`
    # where WORD doesn't match VALID_TOOL_NAMES.
    fuzzy_pattern = re.compile(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[\(\{]",
    )
    for m in fuzzy_pattern.finditer(text):
        name = m.group(1)
        if name in VALID_TOOL_NAMES:
            continue  # already handled above
        # Skip common non-tool words that match the regex
        if name.lower() in {"if", "for", "while", "fn", "let", "match", "use",
                            "pub", "impl", "struct", "enum", "trait", "mod",
                            "return", "true", "false", "self", "super",
                            "function", "def", "lambda", "async", "await"}:
            continue
        tool_from_name = infer_tool_from_name(name)
        # Try parsing trailing args as JSON object first
        rest_start = m.end() - 1  # the `{` or `(`
        if text[rest_start] == "{":
            partial_spans = _find_naked_json_objects(text[rest_start:])
            if not partial_spans:
                continue
            s, e = partial_spans[0]
            args_raw = text[rest_start + s : rest_start + e]
            args = _safe_json_loads(args_raw) or _safe_json_loads(_repair_json(args_raw))
            if isinstance(args, dict):
                # If args has nested {name, arguments} (canonical), unwrap
                if "name" in args and "arguments" in args and isinstance(args.get("arguments"), dict):
                    args = args["arguments"]
                # Infer tool: prefer name signal, fall back to arg shape
                tool = tool_from_name or infer_tool_from_args(args)
                if not tool:
                    continue
                args = remap_args_for_tool(args, tool)
                if args:
                    calls.append(ToolCall(name=tool, args=args))
                    consumed_spans.append((m.start(), rest_start + e))
        else:  # `(`
            # Find matching `)` — simple paren-depth walk
            depth = 1
            j = rest_start + 1
            in_str = False
            quote_ch = None
            escape = False
            while j < len(text) and depth > 0:
                ch = text[j]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == quote_ch:
                        in_str = False
                else:
                    if ch in ('"', "'"):
                        in_str = True
                        quote_ch = ch
                    elif ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                j += 1
            if depth != 0:
                continue
            inner = text[rest_start + 1 : j - 1].strip()
            # Hybrid form: `tool(<json_object>)` — single arg is a JSON object,
            # treat it as the args dict directly (e.g., `andboxed_read({"path": "..."})`)
            if inner.startswith("{"):
                args = _safe_json_loads(inner) or _safe_json_loads(_repair_json(inner))
                if isinstance(args, dict):
                    if "name" in args and "arguments" in args and isinstance(args.get("arguments"), dict):
                        args = args["arguments"]
                    tool = tool_from_name or infer_tool_from_args(args)
                    if not tool:
                        continue
                    args = remap_args_for_tool(args, tool)
                    if args:
                        calls.append(ToolCall(name=tool, args=args))
                        consumed_spans.append((m.start(), j))
                        continue
            args_list = _split_positional_args(inner)
            if not args_list:
                continue
            # Without name signal and no obvious dict-shape args, skip
            tool = tool_from_name
            if not tool:
                continue
            # Heuristic: `open(path, kind)` with 2+ args → glob, not read.
            # The "kind"/"pattern" 2nd positional makes it a list-files intent.
            if tool == "read_file" and len(args_list) >= 2 and "open" in name.lower():
                tool = "glob_files"
            # Map positionally, but our defaults assume tool param order
            param_order = {
                "read_file": ["path"],
                "glob_files": ["path", "pattern"],  # path first when fuzzy ('open(dir, kind)')
                "grep_files": ["pattern", "path"],
                "edit_file": ["path", "old_text", "new_text"],
                "write_file": ["path", "content"],
                "run_command": ["command"],
            }.get(tool, [])
            n_match = min(len(args_list), len(param_order))
            args = {param_order[i]: args_list[i] for i in range(n_match)}
            if args:
                calls.append(ToolCall(name=tool, args=args))
                consumed_spans.append((m.start(), j))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 4c. Last-resort regex extraction: when the model emits Rust-like syntax
    #     `query: "X"`, `scope: Scope::File("Y")`, etc. — JSON parse fails but
    #     the intent is clear. Look for keyword-like fields.
    query_re = re.compile(r'\b(?:query|search|pattern|regex)\s*[:=]\s*"([^"\n]+)"')
    scope_re = re.compile(r'\b(?:scope|path|directory|dir|file|filepath)\s*[:=]\s*'
                          r'(?:[A-Za-z_:]+\(\s*)?"([^"\n]+)"')
    qm = query_re.search(text)
    sm = scope_re.search(text)
    if qm:
        args = {"pattern": qm.group(1)}
        if sm:
            args["path"] = sm.group(1)
        calls.append(ToolCall(name="grep_files", args=args))
        consumed_spans.append((qm.start(), qm.end()))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # 5. "tool_name(positional_arg1, positional_arg2, ...)" — Rust/Python function-call syntax.
    #    Map positional args to known parameter order per tool.
    POSITIONAL_PARAM_ORDER = {
        "read_file": ["path"],
        "glob_files": ["pattern", "path"],
        "grep_files": ["pattern", "path"],
        "edit_file": ["path", "old_text", "new_text"],
        "write_file": ["path", "content"],
        "run_command": ["command"],
    }
    for tool_name in VALID_TOOL_NAMES:
        if tool_name not in POSITIONAL_PARAM_ORDER:
            continue
        # Match `tool_name("arg1", "arg2", ...)` — also tolerate r#"..."# Rust raw strings
        pat = re.compile(
            r"\b" + re.escape(tool_name) + r"\s*\(\s*(.+?)\s*\)",
            re.DOTALL | re.IGNORECASE,
        )
        for m in pat.finditer(text):
            inner = m.group(1)
            args_list = _split_positional_args(inner)
            if not args_list:
                continue
            param_names = POSITIONAL_PARAM_ORDER[tool_name]
            n_match = min(len(args_list), len(param_names))
            args = {param_names[i]: args_list[i] for i in range(n_match)}
            calls.append(ToolCall(name=tool_name, args=args))
            consumed_spans.append((m.start(), m.end()))

    if calls:
        prose = _strip_spans(text, consumed_spans)
        return calls, _clean(prose)

    # Nothing matched — full text is prose
    return [], _clean(text)


def _split_positional_args(inner: str) -> list[str]:
    """Split a function-call argument list, respecting string literals.

    Handles: "regular", 'single', r#"raw"#, multiline strings, comma in strings.
    Returns list of unquoted string values.
    """
    args: list[str] = []
    i = 0
    n = len(inner)
    while i < n:
        # Skip whitespace and commas
        while i < n and inner[i] in " \t\n,":
            i += 1
        if i >= n:
            break
        # Detect Rust raw string: r#"..."#
        if i + 2 < n and inner[i] == "r" and inner[i + 1] == "#" and inner[i + 2] == '"':
            i += 3
            start = i
            while i + 1 < n:
                if inner[i] == '"' and inner[i + 1] == "#":
                    args.append(inner[start:i])
                    i += 2
                    break
                i += 1
            else:
                # Unterminated raw string — take what we have
                args.append(inner[start:])
                break
        elif inner[i] in ('"', "'"):
            quote = inner[i]
            i += 1
            start = i
            buf = []
            while i < n:
                if inner[i] == "\\" and i + 1 < n:
                    buf.append(inner[i + 1])
                    i += 2
                elif inner[i] == quote:
                    args.append("".join(buf) if buf else inner[start:i])
                    i += 1
                    break
                else:
                    buf.append(inner[i])
                    i += 1
            else:
                # Unterminated
                args.append(inner[start:])
                break
        else:
            # Bare identifier / number / object literal — skip until comma or end
            start = i
            depth = 0
            while i < n:
                ch = inner[i]
                if ch in "{[(":
                    depth += 1
                elif ch in "}])":
                    if depth == 0:
                        break
                    depth -= 1
                elif ch == "," and depth == 0:
                    break
                i += 1
            args.append(inner[start:i].strip())
    return args


def _find_naked_json_objects(text: str) -> list[tuple[int, int]]:
    """Find all top-level JSON objects in text via brace-counting.

    Honors string quoting so `{` and `}` inside string values don't affect
    depth. Returns (start, end) spans (end exclusive) for each balanced object.

    When an object opens but never closes (model cut off at max_new_tokens),
    we still emit a span covering [i, n] so the repair logic can attempt to
    close it. _repair_json adds missing braces and quotes.
    """
    spans: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        # Walk forward tracking depth + string state
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
            # Unterminated — emit partial span for repair to attempt
            spans.append((i, n))
            break
    return spans


def _try_parse_tool_call_json(raw: str) -> ToolCall | None:
    """Parse JSON; return ToolCall only if it has a valid name + args/params dict."""
    parsed = _safe_json_loads(raw) or _safe_json_loads(_repair_json(raw))
    if not isinstance(parsed, dict):
        return None
    name = parsed.get("name")
    if not isinstance(name, str) or not name:
        return None
    args = parsed.get("arguments", parsed.get("parameters", {}))
    if not isinstance(args, dict):
        return None
    return ToolCall(name=name, args=args)


def _safe_json_loads(text: str) -> dict | None:
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _repair_json(raw: str) -> str:
    """Repair common malformations: trailing commas, unbalanced braces, unterminated
    strings (when model truncates at max_new_tokens)."""
    text = raw
    # If we're inside a string at end-of-text, close the string.
    # Walk to detect open string state.
    in_string = False
    escape = False
    for ch in text:
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
    if in_string:
        text += '"'

    # Single → double quotes (best-effort; only for unquoted contexts)
    # Note: we DON'T blindly replace ' → " since strings may contain '.
    # Skip quote-replacement when text already has double quotes.
    if '"' not in text:
        text = text.replace("'", '"')

    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    open_count = text.count("{")
    close_count = text.count("}")
    if open_count > close_count:
        text += "}" * (open_count - close_count)
    open_b = text.count("[")
    close_b = text.count("]")
    if open_b > close_b:
        text += "]" * (open_b - close_b)
    return text


def _strip_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Remove the given (start, end) spans from text."""
    if not spans:
        return text
    spans = sorted(spans)
    out = []
    cursor = 0
    for start, end in spans:
        if start > cursor:
            out.append(text[cursor:start])
        cursor = end
    if cursor < len(text):
        out.append(text[cursor:])
    return "".join(out)


def _clean(prose: str) -> str:
    prose = prose.strip()
    prose = re.sub(r"\n{3,}", "\n\n", prose)
    return prose


# ── CLI smoke test ──

if __name__ == "__main__":
    samples = [
        # Canonical (production format)
        '<tool_call>{"name": "read_file", "arguments": {"path": "src/lib.rs"}}</tool_call>',
        # Naked JSON (v2 model's typical output)
        'I will read the file.\n{"name": "read_file", "arguments": {"path": "/tmp/test.rs"}}',
        # Markdown code block with any language label
        'Searching the codebase.\n```typescript\n{"name": "glob_files", "arguments": {"pattern": "*.rs"}}\n```',
        # JSON code block
        'Here goes:\n```json\n{"name": "grep_files", "arguments": {"pattern": "declare_id"}}\n```',
        # Pure prose (no tool call)
        "A PDA is a Program Derived Address that's deterministically derived from a seed and program ID.",
        # Greeting
        "Hello! How can I help you today?",
    ]

    for i, s in enumerate(samples, 1):
        calls, prose = parse(s)
        print(f"=== Sample {i} ===")
        print(f"INPUT: {s[:80]}...")
        print(f"  → {len(calls)} call(s): {[(c.name, c.args) for c in calls]}")
        print(f"  → prose: {prose[:80]!r}")
        print()
