#!/usr/bin/env python3
"""Run Sealevel 80-task eval suite against a live API endpoint.

Usage:
    python training/eval_api.py --api-url http://HOST/v1 --api-key sk-...
    python training/eval_api.py --api-url http://HOST/v1 --api-key sk-... --humaneval
"""
from __future__ import annotations

import json
import re
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

# Load eval tasks from pre-exported JSON (avoids torch dependency)
_data = json.loads((Path(__file__).parent / "eval_tasks.json").read_text())
EVAL_TASKS = _data["tasks"]
SYSTEM_PROMPT = _data["system_prompt"]

# Load extended 120-task eval set
_ext = json.loads((Path(__file__).parent / "eval_tasks_extended.json").read_text())
EVAL_TASKS_EXTENDED = _ext["tasks"]

# Import score_task from extracted file
sys.path.insert(0, str(Path(__file__).parent))
from score_task import score_task


# ---------------------------------------------------------------------------
# HumanEval-mini: 20 coding tasks (language-agnostic, not Solana-specific)
# ---------------------------------------------------------------------------

HUMANEVAL_TASKS = [
    {"id": "he-01", "prompt": "Write a Python function `is_palindrome(s: str) -> bool` that checks if a string is a palindrome, ignoring case and non-alphanumeric characters.", "pass_patterns": [r"def\s+is_palindrome", r"lower|casefold", r"return"], "fail_patterns": []},
    {"id": "he-02", "prompt": "Write a Python function `fibonacci(n: int) -> list[int]` that returns the first n Fibonacci numbers.", "pass_patterns": [r"def\s+fibonacci", r"return", r"\["], "fail_patterns": []},
    {"id": "he-03", "prompt": "Write a Python function `flatten(lst)` that flattens a nested list of arbitrary depth into a single list.", "pass_patterns": [r"def\s+flatten", r"isinstance.*list|recursion|recursive", r"return"], "fail_patterns": []},
    {"id": "he-04", "prompt": "Write a Python function `two_sum(nums: list[int], target: int) -> tuple[int, int]` that returns indices of two numbers that add up to the target.", "pass_patterns": [r"def\s+two_sum", r"return", r"dict|hash|map|\{\}"], "fail_patterns": []},
    {"id": "he-05", "prompt": "Write a Python function `merge_sort(arr: list) -> list` that implements merge sort.", "pass_patterns": [r"def\s+merge_sort|def\s+merge", r"return", r"mid|len.*//\s*2"], "fail_patterns": []},
    {"id": "he-06", "prompt": "Write a Python function `is_valid_parentheses(s: str) -> bool` that checks if parentheses (), [], {} are balanced.", "pass_patterns": [r"def\s+is_valid", r"stack|\[|push|append", r"return"], "fail_patterns": []},
    {"id": "he-07", "prompt": "Write a Python function `binary_search(arr: list[int], target: int) -> int` that returns the index of target or -1.", "pass_patterns": [r"def\s+binary_search", r"mid|lo|hi|left|right", r"return"], "fail_patterns": []},
    {"id": "he-08", "prompt": "Write a Python function `reverse_linked_list(head)` that reverses a singly linked list in place.", "pass_patterns": [r"def\s+reverse", r"prev|next|None", r"return"], "fail_patterns": []},
    {"id": "he-09", "prompt": "Write a Python function `lru_cache(capacity: int)` that implements an LRU cache with get and put methods.", "pass_patterns": [r"class|def\s+lru|OrderedDict|dict", r"get|put|capacity"], "fail_patterns": []},
    {"id": "he-10", "prompt": "Write a Python function `max_subarray(nums: list[int]) -> int` that returns the maximum sum of a contiguous subarray (Kadane's algorithm).", "pass_patterns": [r"def\s+max_subarray|kadane", r"max|current|return"], "fail_patterns": []},
    {"id": "he-11", "prompt": "Write a Python function `count_words(text: str) -> dict[str, int]` that counts word frequencies in a string.", "pass_patterns": [r"def\s+count_words", r"split|dict|\{\}", r"return"], "fail_patterns": []},
    {"id": "he-12", "prompt": "Write a Python function `matrix_multiply(a, b)` that multiplies two 2D matrices.", "pass_patterns": [r"def\s+matrix_multiply|def\s+mat_mul", r"range|for|zip", r"return"], "fail_patterns": []},
    {"id": "he-13", "prompt": "Write a Python function `depth_first_search(graph: dict, start) -> list` that performs DFS on an adjacency list graph.", "pass_patterns": [r"def\s+depth_first|def\s+dfs", r"visited|seen|stack", r"return"], "fail_patterns": []},
    {"id": "he-14", "prompt": "Write a Python function `is_prime(n: int) -> bool` that checks if a number is prime.", "pass_patterns": [r"def\s+is_prime", r"return", r"%|mod|sqrt|range"], "fail_patterns": []},
    {"id": "he-15", "prompt": "Write a Python class `MinHeap` with insert and extract_min methods.", "pass_patterns": [r"class\s+MinHeap", r"insert|push|add", r"extract|pop|min"], "fail_patterns": []},
    {"id": "he-16", "prompt": "Write a Python function `longest_common_subsequence(s1: str, s2: str) -> str` using dynamic programming.", "pass_patterns": [r"def\s+longest_common|def\s+lcs", r"dp|\[\[|table|matrix", r"return"], "fail_patterns": []},
    {"id": "he-17", "prompt": "Write a Python function `serialize_binary_tree(root)` and `deserialize_binary_tree(data)` for a binary tree.", "pass_patterns": [r"def\s+serialize|def\s+deserialize", r"None|null|#", r"queue|deque|split"], "fail_patterns": []},
    {"id": "he-18", "prompt": "Write a Python decorator `retry(max_attempts=3, delay=1)` that retries a function on exception.", "pass_patterns": [r"def\s+retry", r"except|Exception|try", r"wrapper|wraps|functools"], "fail_patterns": []},
    {"id": "he-19", "prompt": "Write a Python async function `fetch_all(urls: list[str])` that fetches multiple URLs concurrently using asyncio.", "pass_patterns": [r"async\s+def|asyncio", r"gather|create_task|aiohttp|httpx", r"await"], "fail_patterns": []},
    {"id": "he-20", "prompt": "Write a Python function `topological_sort(graph: dict) -> list` that returns a topological ordering of a DAG.", "pass_patterns": [r"def\s+topological", r"visited|in_degree|indegree", r"return"], "fail_patterns": []},
]
for t in HUMANEVAL_TASKS:
    t["category"] = "humaneval"


# ---------------------------------------------------------------------------
# API inference
# ---------------------------------------------------------------------------

def generate_via_api(
    client: httpx.Client,
    api_url: str,
    api_key: str,
    prompt: str,
    model: str = "slm-solana",
    max_tokens: int = 512,
    temperature: float = 0.0,
) -> str:
    """Send a chat completion request to the API."""
    resp = client.post(
        f"{api_url}/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logit_bias": {"18471": -30},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run Sealevel eval against live API")
    parser.add_argument("--api-url", required=True, help="API base URL (e.g. http://host/v1)")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--model", default="slm-solana", help="Model name")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--output-dir", default="results/api-eval")
    parser.add_argument("--humaneval", action="store_true", help="Also run 20 HumanEval tasks")
    parser.add_argument("--extended", action="store_true", help="Also run 120 extended Solana tasks")
    args = parser.parse_args()

    tasks = list(EVAL_TASKS)
    if args.extended:
        tasks.extend(EVAL_TASKS_EXTENDED)
    if args.humaneval:
        tasks.extend(HUMANEVAL_TASKS)

    print("=" * 60)
    print("  Sealevel — API Evaluation")
    print("=" * 60)
    print(f"  Endpoint:  {args.api_url}")
    print(f"  Model:     {args.model}")
    solana_count = len(EVAL_TASKS) + (len(EVAL_TASKS_EXTENDED) if args.extended else 0)
    print(f"  Tasks:     {len(tasks)} ({solana_count} Solana" + (f" + {len(HUMANEVAL_TASKS)} HumanEval" if args.humaneval else "") + ")")
    print("=" * 60)

    client = httpx.Client()
    results = []
    category_stats: dict[str, dict] = {}

    for i, task in enumerate(tasks):
        task_id = task["id"]
        category = task["category"]
        prompt = task["prompt"]

        print(f"  [{i+1:3d}/{len(tasks)}] {task_id:12s} ", end="", flush=True)

        t0 = time.time()
        try:
            output = generate_via_api(
                client, args.api_url, args.api_key, prompt,
                model=args.model, max_tokens=args.max_tokens,
                temperature=args.temperature,
            )
        except Exception as e:
            output = f"ERROR: {e}"
            print(f"ERROR ({e})")
            result = {"id": task_id, "category": category, "passed": False,
                      "reason": f"API error: {e}", "output_length": 0, "elapsed_s": 0}
            results.append(result)
            if category not in category_stats:
                category_stats[category] = {"total": 0, "passed": 0}
            category_stats[category]["total"] += 1
            continue

        elapsed = time.time() - t0
        result = score_task(task, output)
        result["elapsed_s"] = round(elapsed, 2)
        result["output_preview"] = output[:200]
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status}  ({elapsed:.1f}s)  {result['reason']}")

        if category not in category_stats:
            category_stats[category] = {"total": 0, "passed": 0}
        category_stats[category]["total"] += 1
        if result["passed"]:
            category_stats[category]["passed"] += 1

    # Aggregate
    total_passed = sum(1 for r in results if r["passed"])
    total_tasks = len(results)
    overall_score = total_passed / total_tasks if total_tasks > 0 else 0.0

    # Separate Solana vs HumanEval scores
    solana_results = [r for r in results if r["category"] != "humaneval"]
    humaneval_results = [r for r in results if r["category"] == "humaneval"]
    solana_passed = sum(1 for r in solana_results if r["passed"])
    humaneval_passed = sum(1 for r in humaneval_results if r["passed"])

    category_scores = {}
    for cat, stats in sorted(category_stats.items()):
        cat_score = stats["passed"] / stats["total"] if stats["total"] > 0 else 0.0
        category_scores[cat] = {
            "passed": stats["passed"],
            "total": stats["total"],
            "score": round(cat_score, 4),
        }

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_url": args.api_url,
        "model": args.model,
        "overall": {"passed": total_passed, "total": total_tasks, "score": round(overall_score, 4)},
        "solana_bench": {"passed": solana_passed, "total": len(solana_results), "score": round(solana_passed / len(solana_results), 4) if solana_results else 0},
        "categories": category_scores,
        "task_results": results,
    }
    if humaneval_results:
        report["humaneval"] = {"passed": humaneval_passed, "total": len(humaneval_results), "score": round(humaneval_passed / len(humaneval_results), 4)}

    # Print summary
    print("\n" + "=" * 60)
    print("  EVAL RESULTS")
    print("=" * 60)
    for cat, cs in sorted(category_scores.items()):
        bar = "#" * int(cs["score"] * 20) + "." * (20 - int(cs["score"] * 20))
        print(f"  {cat:28s}  {cs['passed']:2d}/{cs['total']:2d}  [{bar}] {cs['score']:.1%}")
    print("-" * 60)
    if humaneval_results:
        print(f"  {'SOLANA (80)':28s}  {solana_passed:2d}/{len(solana_results):2d}  {solana_passed/len(solana_results):.1%}")
        print(f"  {'HUMANEVAL (20)':28s}  {humaneval_passed:2d}/{len(humaneval_results):2d}  {humaneval_passed/len(humaneval_results):.1%}")
    print(f"  {'OVERALL':28s}  {total_passed:2d}/{total_tasks:2d}  {overall_score:.1%}")
    print("=" * 60)

    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"eval_api_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
