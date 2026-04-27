"""Shared utilities for tool-calling synthetic data generators.

All generators (gen_tool_calling_*.py) import from here to ensure they emit
records that match the production format byte-for-byte.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Add slm-cli to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "slm-cli"))
sys.path.insert(0, str(ROOT / "scripts"))

from sealevel_cli.agent import AGENT_TOOL_PROMPT, format_tool_results  # noqa: E402
from sealevel_cli.tools import ToolResult  # noqa: E402

from schema import Record  # noqa: E402

# ── Sealevel base system prompt (matches train_sft.py:82-89 exactly) ──
# This is the identical SYSTEM_PROMPT the model was trained with for the 270K
# Solana corpus. Continuing training requires the prefix to match byte-for-byte.

BASE_SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! - these are deprecated."
)


def system_prompt() -> str:
    """The full system prompt that appears in agent-mode training records.

    BASE_SYSTEM_PROMPT + "\n\n" + AGENT_TOOL_PROMPT — matches what
    session.py:286-307 produces at runtime (extra_context = AGENT_TOOL_PROMPT).
    """
    return BASE_SYSTEM_PROMPT + "\n\n" + AGENT_TOOL_PROMPT


def make_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Render a single tool call as the model should emit it.

    Uses canonical formatting: <tool_call>{...}</tool_call> on one line if it
    fits, multiline JSON otherwise. JSON is always valid by construction.
    """
    payload = json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False)
    return f"<tool_call>{payload}</tool_call>"


def make_tool_calls(calls: list[tuple[str, dict[str, Any]]]) -> str:
    """Render multiple tool calls separated by newlines (one per call)."""
    return "\n".join(make_tool_call(name, args) for name, args in calls)


def make_tool_result(name: str, success: bool, output: str) -> str:
    """Render a single <tool_result> block matching agent.py:66-76 exactly."""
    status = "success" if success else "error"
    return f'<tool_result name="{name}" status="{status}">\n{output}\n</tool_result>'


def make_tool_results(results: list[tuple[str, bool, str]]) -> str:
    """Render multiple tool results joined by '\n\n' (matches agent.py:76)."""
    return "\n\n".join(make_tool_result(name, success, output) for name, success, output in results)


def assistant_with_calls(prose_before: str, calls: list[tuple[str, dict]]) -> str:
    """Compose an assistant turn that contains optional prose then tool calls.

    The training invariant: a turn either has tool calls (and minimal narration
    before them) OR is the final answer (no tool calls). Never mix.
    """
    rendered_calls = make_tool_calls(calls)
    if prose_before:
        return f"{prose_before}\n{rendered_calls}"
    return rendered_calls


def build_messages(
    user_msg: str,
    trajectory: list[tuple[str, list[tuple[str, dict]] | str]],
    final: str,
) -> list[dict]:
    """Build the full messages array for a multi-turn record.

    `trajectory` alternates between assistant-tool turns and user-result turns:
      - Each entry is (kind, payload) where kind is "assistant" or "user".
      - For "assistant", payload is (prose_before, [(tool_name, args), ...]).
      - For "user", payload is the rendered tool_result string OR a list of
        (name, success, output) tuples that this helper renders.

    `final` is the last assistant message — pure prose, no tool calls.

    Returns the messages array including system + initial user + trajectory + final.
    """
    messages: list[dict] = [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_msg},
    ]

    for kind, payload in trajectory:
        if kind == "assistant":
            prose, calls = payload  # type: ignore
            messages.append({"role": "assistant", "content": assistant_with_calls(prose, calls)})
        elif kind == "user":
            if isinstance(payload, list):
                content = make_tool_results(payload)  # type: ignore
            else:
                content = payload  # already rendered string
            messages.append({"role": "user", "content": content})
        else:
            raise ValueError(f"Unknown trajectory kind: {kind}")

    messages.append({"role": "assistant", "content": final})
    return messages


def make_record(
    messages: list[dict],
    category: str,
    subcategory: str = "",
    metadata_extra: dict | None = None,
) -> Record:
    """Wrap messages into a Record matching the existing dataset schema."""
    payload = {"messages": messages}
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    # Count tool calls and iterations for metadata
    tool_calls_total = 0
    iterations = 0
    for msg in messages:
        if msg["role"] == "assistant":
            iterations += 1
            tool_calls_total += msg["content"].count("<tool_call>")

    metadata = {
        "method": "tool_calling_v1",
        "category": category,
        "subcategory": subcategory,
        "tool_calls_total": tool_calls_total,
        "iterations": iterations,
        "verified_parser": False,  # set True after verify_tool_calling.py runs
        "verified_schema": False,
        "collected_at": date.today().isoformat(),
    }
    if metadata_extra:
        metadata.update(metadata_extra)

    return Record(
        id=Record.make_id(content),
        source="synthetic/tool_calling",
        source_type="qa",
        content=content,
        language="en",
        license="synthetic-mit",
        metadata=metadata,
    )


def execute_tool_for_real(name: str, args: dict, cwd: Path) -> ToolResult:
    """Run the actual production tool executor and return its result.

    This guarantees the tool_result content in our training data matches what
    the model will see at inference time exactly (line numbers, error messages,
    output capping, etc).
    """
    from sealevel_cli.tools import execute  # imported lazily

    return execute(name, args, cwd=cwd)


# ── Common phrasings (used across multiple generators) ──

# "Read this file" phrasings — used by Group A1, J1
READ_PHRASINGS = [
    "Read {path}.",
    "Show me {path}.",
    "What's in {path}?",
    "Open {path} for me.",
    "Display the contents of {path}.",
    "Can you show me {path}?",
    "I want to see {path}.",
    "View {path}.",
    "Print {path}.",
    "What does {path} contain?",
    "Look at {path}.",
    "Fetch the contents of {path}.",
]

# "Find files matching" phrasings
GLOB_PHRASINGS = [
    "Find all {pattern} files.",
    "List every {pattern} file.",
    "Show me all {pattern} files in this project.",
    "What {pattern} files exist?",
    "Get me all {pattern} files.",
    "Search for {pattern} files.",
    "Where are the {pattern} files?",
    "Locate every {pattern} file.",
]

# "Search content" phrasings
GREP_PHRASINGS = [
    "Search for `{pattern}` in the codebase.",
    "Find usages of `{pattern}`.",
    "Where is `{pattern}` used?",
    "Look for `{pattern}` in the source.",
    "Grep for `{pattern}`.",
    "Find `{pattern}` references.",
    "Show me where `{pattern}` appears.",
    "Search the code for `{pattern}`.",
]

# Greetings / no-tool prompts
GREETINGS = [
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
    "great, thanks",
    "good morning",
    "hi there",
    "hey, how are you?",
    "ok, got it",
]


def write_records_to_jsonl(records: list[Record], path: Path) -> None:
    """Write records to JSONL, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(r.to_json() + "\n")
    print(f"Wrote {len(records)} records to {path}")
