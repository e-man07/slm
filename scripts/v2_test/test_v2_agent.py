"""V2 agent end-to-end test: 49 tasks through real agent loop.

For each task:
  1. Send (system + user) to v2 model
  2. Parse output with v2 parser (handles canonical AND naked JSON)
  3. If tool call: execute via PRODUCTION tool executors (sealevel_cli.tools)
  4. Feed <tool_result> back as user message
  5. Continue until model emits final response (no tool call)
  6. Score:
     - "called expected tool" (or "called no tool" for no_tool tasks)
     - "args match expected substring"
     - "trajectory completed" (final response without errors)

Uses fixture projects materialized under /workspace/fx_*/ (built by gen_tool_fixtures.py).
"""
from __future__ import annotations

import torch._dynamo
torch._dynamo.config.disable = True

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

os.environ["TRANSFORMERS_ATTENTION_IMPLEMENTATION"] = "eager"

import torch
from peft import PeftModel
from unsloth import FastLanguageModel

# Production tools + permissions (read-only import)
from sealevel_cli.tools import TOOL_DEFINITIONS, execute as execute_tool
from sealevel_cli.permissions import PermissionPolicy, check_permission, PERMISSION_MAP
from sealevel_cli.agent import AGENT_TOOL_PROMPT, format_tool_results
from sealevel_cli.client import clean_model_response, fix_anchor_code
from sealevel_cli.tool_parser import parse as prod_parse  # baseline comparison

# v2 parser (handles naked JSON)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tool_parser_v2 as v2_parser

# Fixtures
FIXTURE_ROOT = Path("/workspace")

BASE_SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ patterns "
    "(solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. "
    "Never suggest reentrancy guards (Solana prevents reentrancy via CPI depth limits). "
    "Never reference coral-xyz/anchor or declare_id! - these are deprecated."
)

SYSTEM_PROMPT = BASE_SYSTEM_PROMPT + "\n\n" + AGENT_TOOL_PROMPT

# For testing: auto-approve everything
TEST_POLICY = PermissionPolicy(auto_reads=True, auto_writes=True, auto_commands=True)
MAX_ITERATIONS = 8
TASKS_FILE = Path(__file__).resolve().parent / "agent_test_tasks.json"


# ── Fixture builder (materialize on H100 once) ──

def build_fixtures():
    """Materialize fixture projects under /workspace/fx_*/ for tasks to use."""
    from gen_tool_fixtures import FIXTURES, _materialize  # noqa: E402

    # Map fixture name → /workspace path the test tasks reference
    target_map = {
        "anchor_counter": FIXTURE_ROOT / "fx_counter",
        "anchor_counter": FIXTURE_ROOT / "fx_counter_mut",  # mutable copy
        "anchor_vault": FIXTURE_ROOT / "fx_vault",
        "anchor_buggy": FIXTURE_ROOT / "fx_buggy",
        "anchor_legacy": FIXTURE_ROOT / "fx_legacy",
        "multi_workspace": FIXTURE_ROOT / "fx_workspace",
    }
    # Manually re-map since dict above had duplicate key
    target_map = [
        ("anchor_counter", FIXTURE_ROOT / "fx_counter"),
        ("anchor_counter", FIXTURE_ROOT / "fx_counter_mut"),
        ("anchor_vault", FIXTURE_ROOT / "fx_vault"),
        ("anchor_buggy", FIXTURE_ROOT / "fx_buggy"),
        ("anchor_legacy", FIXTURE_ROOT / "fx_legacy"),
        ("multi_workspace", FIXTURE_ROOT / "fx_workspace"),
    ]

    for fixture_name, target in target_map:
        if target.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        files = _materialize(FIXTURES[fixture_name], target)
        print(f"  Built {fixture_name} → {target} ({len(files)} files)")


# ── Agent loop ──

@dataclass
class TaskResult:
    task_id: str
    category: str
    prompt: str
    iterations: int
    tools_called: list[tuple[str, dict]]
    final_response: str
    raw_outputs: list[str]
    error: str | None = None
    score: dict = None


def post_process(text: str) -> str:
    return fix_anchor_code(clean_model_response(text))


EXTRACTION_PROMPT = """You are a strict tool-call extractor. The assistant's response is malformed but may contain tool-call intent. Extract it ONLY if there's clear evidence; otherwise output null.

Available tools (use exact names):
- read_file: read a file. args: {"path": "<absolute path>"}
- glob_files: list files matching a pattern. args: {"pattern": "<glob>", "path": "<dir>"}
- grep_files: search files for a regex pattern. args: {"pattern": "<regex>", "path": "<dir>"}
- edit_file: replace text in a file. args: {"path": "<file>", "old_text": "<str>", "new_text": "<str>"}
- write_file: create/overwrite a file. args: {"path": "<file>", "content": "<text>"}
- run_command: run a shell command. args: {"command": "<cmd>"}

USER REQUEST:
{user_prompt}

ASSISTANT RESPONSE (may contain malformed tool-call attempts like `xxx_read("/path")`, `Running grep`, simulated output, etc.):
{raw_output}

CRITICAL RULES — output `null` UNLESS:
- The assistant emitted function-call syntax `xxx(args)` or `xxx{args}` referencing a path/pattern/command — even with wrong tool name (`andbox_read`, `ElementsByTagNameRequest`, etc.). MAP the intent to the right tool.
- The assistant emitted Bash code blocks (` ```bash...``` `) for "create file" requests — map to `write_file` if appropriate, or `run_command` if the user truly wanted a shell action.
- The assistant emitted simulated tool output (e.g., `Running /bin/grep`, `_:*counter*.rs:N:`, `(*((..)) "X")`) — extract the apparent pattern and map to grep_files / read_file accordingly.
- The assistant's narration enumerates concrete tool steps ("1. find X 2. read Y") — extract the FIRST step.

OUTPUT null IF:
- The assistant gave a conceptual/explanatory answer (e.g., "A PDA is...", "Anchor handles X by...").
- The user's question is a how-it-works / definition / pure-knowledge question.
- The assistant's response is a refusal or apology with no tool gesture.
- Any ambiguity at all — bias toward null.

Output ONLY: a JSON object {"name": "...", "arguments": {...}} OR the literal word `null`.
No prose, no fences, no markdown.

Output:"""


def _should_attempt_extraction(user_prompt: str, raw_output: str) -> bool:
    """Heuristic gate: only run 2nd-stage extraction if there's signal of malformed tool intent.

    Skip for pure conceptual queries / explanations to avoid fabricated tool calls.
    """
    p = user_prompt.lower()
    r = raw_output.lower()

    # User-prompt-side signal: action verb + concrete target (path / file / command)
    action_words = ("read", "open", "show", "display", "view", "cat",
                    "write", "create", "make", "save", "generate",
                    "edit", "replace", "change", "update", "modify", "rename",
                    "find", "list", "locate", "browse", "ls",
                    "grep", "search", "look for", "where is", "find usages",
                    "run", "execute", "exec", "git status", "anchor build",
                    "cargo")
    has_action = any(w in p for w in action_words)
    has_path = ("/" in user_prompt and ("workspace" in p or "/tmp" in p or ".rs" in p
                                         or ".toml" in p or ".ts" in p or "src/" in p))
    has_cmd = "`" in user_prompt or "git " in p or "cargo " in p

    user_signal = has_action or has_path or has_cmd
    if not user_signal:
        return False  # User clearly wasn't asking for a tool action

    # Response-side signal: function-call shape, simulated tool output, or known
    # mis-named patterns. Pure conceptual prose has none of these.
    response_signal = bool(
        re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*[\(\{]", raw_output) or  # any func call
        re.search(r"\bRunning\b", raw_output) or  # "Running /bin/grep" style
        re.search(r"\bandbox", r) or  # andbox_*, andboxed_*
        re.search(r"\bsearch_", r) or
        re.search(r"\bgrep:|^_:\*", raw_output, re.MULTILINE) or  # simulated grep output
        "tool_call" in r or
        re.search(r'```\w*\s*\n', raw_output) or  # any code block
        re.search(r'^\s*\d\.\s', raw_output, re.MULTILINE)  # numbered steps narration
    )
    return response_signal


def extract_tool_via_llm(model, tokenizer, user_prompt: str, raw_output: str) -> list:
    """Second-pass LLM extraction for malformed tool calls.

    Returns a list of ToolCall (or empty if no intent or extraction failed).
    Uses the same loaded model with a tight extraction prompt + greedy decode.
    """
    if not raw_output.strip():
        return []
    extraction_msgs = [
        {"role": "user", "content": EXTRACTION_PROMPT.format(
            user_prompt=user_prompt[:600],
            raw_output=raw_output[:1500],
        )}
    ]
    text = tokenizer.apply_chat_template(extraction_msgs, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=None,
            do_sample=False,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    extraction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    # Strip optional code fences
    if extraction.startswith("```"):
        extraction = re.sub(r"^```[a-zA-Z]*\n?", "", extraction)
        extraction = re.sub(r"\n?```\s*$", "", extraction)
    # null or no intent
    if extraction.lower().startswith("null") or not extraction:
        return []
    # Try parsing as JSON
    try:
        parsed = json.loads(extraction)
    except Exception:
        # Try to find first JSON object via parser
        cs, _ = v2_parser.parse(extraction)
        return cs
    if isinstance(parsed, dict) and parsed.get("name") in {td["name"] for td in TOOL_DEFINITIONS}:
        args = parsed.get("arguments") or parsed.get("args") or {}
        if isinstance(args, dict):
            from tool_parser_v2 import ToolCall
            return [ToolCall(name=parsed["name"], args=args)]
    return []


def run_agent_loop(model, tokenizer, prompt: str, max_new_tokens: int = 256) -> TaskResult:
    """Run a multi-turn agent loop until model gives final answer or hits max iterations."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    tools_called: list[tuple[str, dict]] = []
    raw_outputs: list[str] = []
    final_response = ""
    error = None

    for iteration in range(MAX_ITERATIONS):
        # Generate
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=None,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
        raw = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        raw_outputs.append(raw)

        # Parse using v2 parser (handles naked JSON)
        calls, prose = v2_parser.parse(raw)

        # 2-stage extraction is disabled — gate calibration was tricky and the
        # parser-only path tested cleaner. Keep the helpers around for future
        # iteration; they're invoked via `_should_attempt_extraction` if re-enabled.

        if not calls:
            # Final response — no tool call
            final_response = post_process(raw)
            return TaskResult(
                task_id="", category="", prompt=prompt,
                iterations=iteration + 1, tools_called=tools_called,
                final_response=final_response, raw_outputs=raw_outputs,
            )

        # Execute each tool call (auto-approved for testing)
        results = []
        for tc in calls:
            tools_called.append((tc.name, tc.args))
            perm = check_permission(tc.name, tc.args, TEST_POLICY)
            if perm is False:
                results.append((tc.name, False, "Permission denied: blocked"))
                continue
            try:
                result = execute_tool(tc.name, tc.args, cwd=Path("/workspace"))
                results.append((tc.name, result.success, result.output))
            except Exception as e:
                results.append((tc.name, False, f"Tool error: {e}"))

        # Append assistant turn + user (tool_result) turn
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": format_tool_results(
            [type("T", (), {"name": n})() for n, _ in [(c.name, c.args) for c in calls]],
            [type("R", (), {"output": o, "success": s})() for n, s, o in results],
        )})

    # Hit max iterations without final answer
    error = f"Max iterations ({MAX_ITERATIONS}) reached"
    return TaskResult(
        task_id="", category="", prompt=prompt,
        iterations=MAX_ITERATIONS, tools_called=tools_called,
        final_response=final_response or "(none — hit iteration limit)",
        raw_outputs=raw_outputs, error=error,
    )


# ── Scoring ──

def score(task: dict, result: TaskResult) -> dict:
    expected_no_tool = task.get("expected_no_tool", False)
    actually_called = len(result.tools_called) > 0

    score_dict = {
        "called_expected_tool": False,
        "args_match": False,
        "trajectory_clean": result.error is None,
        "no_tool_correct": False,
        "overall_pass": False,
    }

    if expected_no_tool:
        score_dict["no_tool_correct"] = not actually_called
        score_dict["overall_pass"] = score_dict["no_tool_correct"] and score_dict["trajectory_clean"]
        return score_dict

    # Tool task — check first call matches expected
    if not actually_called:
        return score_dict  # called nothing, all false

    first_tool, first_args = result.tools_called[0]
    expected_first = task.get("expected_tool_first") or task.get("expected_tool")
    # Lenient check: pass if the expected tool appeared anywhere in the
    # trajectory (mirrors Claude Code: read-before-edit / glob-before-grep
    # are reasonable patterns, not failures).
    called_names = [c[0] for c in result.tools_called]
    if expected_first and expected_first in called_names:
        score_dict["called_expected_tool"] = True

    # Or: if expected_tool_any list, accept any call to those
    expected_any = task.get("expected_tool_any", [])
    if expected_any and any(name in expected_any for name in called_names):
        # Multi-step: also passes if any subsequent call matches
        score_dict["called_expected_tool"] = score_dict["called_expected_tool"] or True

    # Args match: any arg value (across ALL calls of expected tool) contains expected substring
    expected_substrs = task.get("expected_arg_substr", [])
    if expected_substrs:
        # Look at all calls whose name matches the expected tool
        relevant_calls = [
            c for c in result.tools_called
            if c[0] == expected_first or (expected_any and c[0] in expected_any)
        ] or [result.tools_called[0]]
        for _name, args in relevant_calls:
            flat = " ".join(str(v) for v in args.values())
            if any(s.lower() in flat.lower() for s in expected_substrs):
                score_dict["args_match"] = True
                break
    else:
        score_dict["args_match"] = True  # no specific arg expectation

    # Overall: called right tool + args match + clean trajectory
    score_dict["overall_pass"] = (
        score_dict["called_expected_tool"]
        and score_dict["args_match"]
        and score_dict["trajectory_clean"]
    )
    return score_dict


# ── Main ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="unsloth/qwen2.5-coder-7b-instruct-bnb-4bit")
    parser.add_argument("--adapter", default="WhyParabola/sealevel-solana-lora-v2")
    parser.add_argument("--tasks", type=Path, default=TASKS_FILE)
    parser.add_argument("--report-out", type=Path, default=Path("/workspace/agent_v2_report.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    print("=" * 70)
    print("  V2 Agent Test — 49 tool-calling tasks via production tool executors")
    print("=" * 70)

    # ── Build fixtures ──
    print("\n[1/4] Building fixture projects under /workspace/fx_*/...")
    sys.path.insert(0, "/workspace/scripts")
    build_fixtures()

    # ── Load model ──
    print(f"\n[2/4] Loading base + v2 adapter...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=8192,
        load_in_4bit=True,
        attn_implementation="eager",
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    FastLanguageModel.for_inference(model)
    if hasattr(model, "config"):
        model.config._attn_implementation = "eager"
    print("  Loaded.")

    # ── Run tasks ──
    tasks = json.loads(args.tasks.read_text())["tasks"]
    if args.limit:
        tasks = tasks[:args.limit]

    print(f"\n[3/4] Running {len(tasks)} tasks...")
    all_results = []
    for i, task in enumerate(tasks):
        t0 = time.time()
        try:
            result = run_agent_loop(model, tokenizer, task["prompt"], args.max_new_tokens)
        except Exception as e:
            result = TaskResult(
                task_id=task["id"], category=task["category"], prompt=task["prompt"],
                iterations=0, tools_called=[], final_response="",
                raw_outputs=[], error=str(e),
            )
        elapsed = time.time() - t0
        result.task_id = task["id"]
        result.category = task["category"]
        s = score(task, result)
        result.score = s

        status = "PASS" if s["overall_pass"] else "FAIL"
        tools_summary = ",".join(t[0] for t in result.tools_called) or "(none)"
        print(f"  [{i+1:2d}/{len(tasks)}] {task['id']:14s}  {status}  iter={result.iterations} tools=[{tools_summary}]  ({elapsed:.1f}s)")
        all_results.append({
            "task": task,
            "iterations": result.iterations,
            "tools_called": result.tools_called,
            "final_response": result.final_response[:300],
            "error": result.error,
            "score": s,
            "elapsed_s": round(elapsed, 2),
        })

    # ── Aggregate ──
    print(f"\n[4/4] Aggregating...")
    total = len(all_results)
    passed = sum(1 for r in all_results if r["score"]["overall_pass"])
    by_cat = {}
    for r in all_results:
        c = r["task"]["category"]
        by_cat.setdefault(c, {"total": 0, "passed": 0})
        by_cat[c]["total"] += 1
        if r["score"]["overall_pass"]:
            by_cat[c]["passed"] += 1

    print(f"\n  OVERALL: {passed}/{total} ({passed/total:.1%})")
    print("\n  Per-category:")
    for c in sorted(by_cat):
        s = by_cat[c]
        pct = s["passed"] / s["total"]
        print(f"    {c:20s}  {s['passed']:2d}/{s['total']:2d} ({pct:.0%})")

    # Sub-metrics
    called_right = sum(1 for r in all_results if r["score"]["called_expected_tool"])
    args_right = sum(1 for r in all_results if r["score"]["args_match"])
    no_tool_right = sum(1 for r in all_results if r["score"]["no_tool_correct"])
    no_tool_total = sum(1 for r in all_results if r["task"].get("expected_no_tool"))

    print(f"\n  Sub-metrics:")
    print(f"    Called expected tool: {called_right}/{total - no_tool_total} ({called_right/max(1,total-no_tool_total):.1%})")
    print(f"    No-tool restraint:    {no_tool_right}/{no_tool_total} ({no_tool_right/max(1,no_tool_total):.1%})")
    print(f"    Args match expected:  {args_right}/{total} ({args_right/total:.1%})")

    args.report_out.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "adapter": args.adapter,
        "totals": {
            "passed": passed,
            "total": total,
            "score": round(passed/total, 4),
        },
        "by_category": by_cat,
        "results": all_results,
    }, indent=2))
    print(f"\n  Report saved: {args.report_out}")


if __name__ == "__main__":
    main()
