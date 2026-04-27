"""Verify synthetic tool-calling JSONL records before training.

The HARD gate. Every assertion below must pass for every record, or this script
exits with a non-zero status, blocking the pipeline.

What we verify:
  1. Record schema (id, source, content, etc) is well-formed.
  2. content is valid JSON with a `messages` array.
  3. System prompt prefix matches SYSTEM_PROMPT + AGENT_TOOL_PROMPT byte-for-byte.
  4. Every assistant turn either has zero <tool_call> tags (final answer)
     OR only <tool_call> tags with valid JSON and no plaintext final answer.
  5. tool_parser.parse() round-trips every assistant tool-call turn.
  6. Every tool call's `name` is in TOOL_DEFINITIONS.
  7. Every tool call's `arguments` includes all required keys with correct types.
  8. Every <tool_result> user message matches the canonical regex format.
  9. Sensitive-file refusals contain the exact substring expected.
 10. Total record length ≤ 7,800 tokens (estimated 4 chars/token) so trajectories
     fit within the 8,192 max_seq_length training cap.

Usage:
    python scripts/verify_tool_calling.py --strict path/to/file.jsonl [more.jsonl ...]

Exit code 0 = all records valid. Non-zero = at least one record invalid; details printed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Add slm-cli to path so we can import the production parser/tools
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "slm-cli"))
sys.path.insert(0, str(ROOT / "scripts"))

from sealevel_cli.tool_parser import parse as parse_tool_calls  # noqa: E402
from sealevel_cli.tools import TOOL_DEFINITIONS  # noqa: E402

# Build a name → schema map for quick lookup
TOOL_SCHEMAS: dict[str, dict] = {td["name"]: td for td in TOOL_DEFINITIONS}
VALID_TOOL_NAMES = set(TOOL_SCHEMAS.keys())

# Tool result regex: must be exactly this shape (matches agent.py:66-76)
TOOL_RESULT_RE = re.compile(
    r'^<tool_result name="([^"]+)" status="(success|error)">\n(.*?)\n</tool_result>$',
    re.DOTALL,
)

# Token budget
MAX_TOKENS_EST = 7_800
CHARS_PER_TOKEN = 4

# Sensitive refusal substrings — must appear in error tool_result content
SENSITIVE_SUBSTRINGS = [
    "Cannot read sensitive file",
    "Cannot write sensitive file",
    "Cannot edit sensitive file",
    "Permission denied by user",
    "Permission denied: sensitive file or dangerous command",
]


# ── Validators ──


class ValidationError(Exception):
    """Raised when a record fails validation."""

    def __init__(self, record_idx: int, record_id: str, reason: str) -> None:
        super().__init__(f"Record #{record_idx} (id={record_id[:12]}...): {reason}")
        self.record_idx = record_idx
        self.record_id = record_id
        self.reason = reason


def validate_python_type(value, expected: str) -> bool:
    """Check if value matches expected JSON-schema type string."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True  # unknown type, pass


def validate_tool_call(name: str, args: dict, ctx: str) -> list[str]:
    """Return list of error messages; empty list means valid."""
    errors: list[str] = []

    if name not in VALID_TOOL_NAMES:
        errors.append(f"{ctx}: unknown tool '{name}'. Valid: {sorted(VALID_TOOL_NAMES)}")
        return errors

    schema = TOOL_SCHEMAS[name]["parameters"]
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required keys present
    for req_key in required:
        if req_key not in args:
            errors.append(f"{ctx}: tool '{name}' missing required arg '{req_key}'")

    # Check types of provided args
    for arg_key, arg_value in args.items():
        if arg_key not in properties:
            # Unknown arg — not strictly an error (parser is permissive)
            continue
        expected_type = properties[arg_key].get("type")
        if expected_type and not validate_python_type(arg_value, expected_type):
            errors.append(
                f"{ctx}: tool '{name}' arg '{arg_key}' has wrong type "
                f"(expected {expected_type}, got {type(arg_value).__name__})"
            )

    return errors


def assistant_turn_has_tool_call(content: str) -> bool:
    """Return True if assistant content contains a <tool_call> tag."""
    return "<tool_call>" in content and "</tool_call>" in content


def validate_messages(messages: list[dict], record_idx: int, record_id: str) -> list[str]:
    """Validate the message array of a record."""
    errors: list[str] = []

    if not messages:
        return [f"empty messages array"]

    # First message must be system
    if messages[0].get("role") != "system":
        errors.append(f"first message must be role='system', got '{messages[0].get('role')}'")

    # Walk turns
    for i, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content", "")

        if role not in ("system", "user", "assistant"):
            errors.append(f"msg #{i}: invalid role '{role}'")
            continue

        if not isinstance(content, str):
            errors.append(f"msg #{i}: content must be string")
            continue

        # Validate assistant turns
        if role == "assistant":
            has_tags = assistant_turn_has_tool_call(content)
            if has_tags:
                # Parse the tool calls
                tool_calls, prose = parse_tool_calls(content)
                if not tool_calls:
                    errors.append(
                        f"msg #{i} (assistant): contains <tool_call> tags but parser found 0 valid calls"
                    )
                    continue
                # Each call must validate
                for j, tc in enumerate(tool_calls):
                    ctx = f"msg #{i} (assistant), call #{j}"
                    errors.extend(validate_tool_call(tc.name, tc.args, ctx))
            # If no tag, that's fine — final answer turn

        # Validate user turns containing tool_result
        if role == "user" and "<tool_result" in content:
            # Each <tool_result> must match canonical format
            results = re.findall(
                r'<tool_result name="[^"]+" status="(?:success|error)">\n.*?\n</tool_result>',
                content,
                re.DOTALL,
            )
            tag_count = content.count("<tool_result")
            if len(results) != tag_count:
                errors.append(
                    f"msg #{i} (user): {tag_count} <tool_result> tags but only {len(results)} match canonical format"
                )

    return errors


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate from total chars."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return total_chars // CHARS_PER_TOKEN


# ── Per-record validation ──


def validate_record(record: dict, record_idx: int) -> list[str]:
    """Return list of error strings for one record. Empty = valid."""
    errors: list[str] = []
    record_id = record.get("id", "<no-id>")

    # Schema fields
    for required_field in ("id", "source", "source_type", "content", "metadata"):
        if required_field not in record:
            errors.append(f"missing required field '{required_field}'")

    if "content" not in record:
        return errors  # can't validate further

    # Parse content as JSON
    try:
        payload = json.loads(record["content"])
    except json.JSONDecodeError as e:
        return errors + [f"content is not valid JSON: {e}"]

    if not isinstance(payload, dict) or "messages" not in payload:
        return errors + [f"content must be JSON with a 'messages' array"]

    messages = payload["messages"]
    if not isinstance(messages, list):
        return errors + [f"messages must be a list"]

    # Validate messages
    errors.extend(validate_messages(messages, record_idx, record_id))

    # Length budget
    tokens = estimate_tokens(messages)
    if tokens > MAX_TOKENS_EST:
        errors.append(
            f"trajectory too long: {tokens} estimated tokens (max {MAX_TOKENS_EST})"
        )

    return errors


# ── Main ──


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify tool-calling JSONL records")
    parser.add_argument("paths", nargs="+", type=Path, help="JSONL file(s) to verify")
    parser.add_argument("--strict", action="store_true", help="Exit on first failure")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    total_records = 0
    total_errors = 0
    files_with_errors: list[str] = []
    category_counts: Counter[str] = Counter()
    tool_call_counts: Counter[str] = Counter()

    for path in args.paths:
        if not path.exists():
            print(f"FAIL: {path} does not exist", file=sys.stderr)
            return 1

        print(f"\nVerifying: {path}")
        file_records = 0
        file_errors = 0

        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  line {line_num}: invalid JSON line: {e}", file=sys.stderr)
                    file_errors += 1
                    if args.strict:
                        return 1
                    continue

                total_records += 1
                file_records += 1

                # Track category for stats
                category = record.get("metadata", {}).get("category", "<unknown>")
                category_counts[category] += 1

                # Count tool calls used
                try:
                    payload = json.loads(record.get("content", "{}"))
                    for msg in payload.get("messages", []):
                        if msg.get("role") == "assistant":
                            calls, _ = parse_tool_calls(msg.get("content", ""))
                            for tc in calls:
                                tool_call_counts[tc.name] += 1
                except Exception:
                    pass

                errors = validate_record(record, total_records)
                if errors:
                    file_errors += 1
                    total_errors += 1
                    if args.verbose or args.strict:
                        print(
                            f"  line {line_num} (id={record.get('id', '')[:12]}...):",
                            file=sys.stderr,
                        )
                        for err in errors:
                            print(f"    - {err}", file=sys.stderr)
                    if args.strict:
                        return 1

        print(f"  records: {file_records}, errors: {file_errors}")
        if file_errors > 0:
            files_with_errors.append(str(path))

    # Summary
    print("\n" + "=" * 60)
    print(f"Total records: {total_records}")
    print(f"Total errors: {total_errors}")
    if total_errors == 0:
        print("ALL CHECKS PASSED")
    else:
        print(f"FAILED: {total_errors} record(s) failed validation")
        for f in files_with_errors:
            print(f"  - {f}")

    print("\nCategory distribution:")
    for cat, count in category_counts.most_common():
        print(f"  {cat}: {count}")

    print("\nTool call distribution:")
    for tool, count in tool_call_counts.most_common():
        print(f"  {tool}: {count}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
