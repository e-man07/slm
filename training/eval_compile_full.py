#!/usr/bin/env python3
"""Run all 230 eval tasks and try to compile any that produce Rust code."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from eval_compile import extract_rust_code, fixup_code, SYSTEM_PROMPT

# Load all tasks
_data = json.loads((Path(__file__).parent / "eval_tasks.json").read_text())
_ext = json.loads((Path(__file__).parent / "eval_tasks_extended.json").read_text())
from eval_compile import COMPILE_TASKS

# Load anchor patterns for system prompt
_patterns_path = Path(__file__).parent.parent / "deploy" / "rag-api" / "anchor_patterns.md"
_patterns = _patterns_path.read_text() if _patterns_path.exists() else ""

ALL_TASKS = _data["tasks"] + _ext["tasks"]

# HumanEval tasks (Python, not Rust)
HUMANEVAL_TASKS = []
try:
    from eval_api import HUMANEVAL_TASKS
except:
    pass


def generate(client, api_url, api_key, prompt, model="slm-solana", max_tokens=1024):
    resp = client.post(
        f"{api_url}/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "logit_bias": {"18471": -30},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def try_compile(code: str, project_dir: str) -> tuple[bool, str]:
    code = fixup_code(code)
    lib_path = Path(project_dir) / "programs" / "bench_project" / "src" / "lib.rs"
    lib_path.write_text(code)
    result = subprocess.run(
        ["cargo", "check", "--manifest-path",
         str(Path(project_dir) / "programs" / "bench_project" / "Cargo.toml")],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        return True, ""
    errors = [l for l in result.stderr.split('\n') if 'error' in l.lower()]
    return False, errors[0][:120] if errors else result.stderr[:120]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="slm-solana")
    parser.add_argument("--project-dir", default="/tmp/slm-bench/bench_project")
    parser.add_argument("--output-dir", default="results/compile-eval")
    args = parser.parse_args()

    # Combine all tasks
    tasks = ALL_TASKS + COMPILE_TASKS
    # Deduplicate by id
    seen = set()
    unique_tasks = []
    for t in tasks:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique_tasks.append(t)
    tasks = unique_tasks

    print("=" * 70)
    print("  Sealevel — Full Compilation Benchmark (all tasks)")
    print("=" * 70)
    print(f"  Tasks: {len(tasks)}")
    print("=" * 70)

    client = httpx.Client()
    results = []
    compiled = 0
    failed = 0
    no_code = 0
    total_with_code = 0

    for i, task in enumerate(tasks):
        tid = task["id"]
        prompt = task.get("prompt", "")
        cat = task.get("category", "")

        print(f"  [{i+1:3d}/{len(tasks)}] {tid:16s} ", end="", flush=True)

        t0 = time.time()
        try:
            response = generate(client, args.api_url, args.api_key, prompt, args.model)
        except Exception as e:
            print(f"API_ERR")
            results.append({"id": tid, "category": cat, "has_code": False, "compiled": False, "reason": str(e)})
            continue

        code = extract_rust_code(response)
        elapsed = time.time() - t0

        if not code:
            no_code += 1
            print(f"NO_RUST  ({elapsed:.1f}s)")
            results.append({"id": tid, "category": cat, "has_code": False, "compiled": False, "reason": "no rust code"})
            continue

        total_with_code += 1
        try:
            compiles, err = try_compile(code, args.project_dir)
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT  ({elapsed:.1f}s)")
            results.append({"id": tid, "category": cat, "has_code": True, "compiled": False, "reason": "timeout"})
            failed += 1
            continue

        elapsed = time.time() - t0
        if compiles:
            compiled += 1
            print(f"COMPILE  ({elapsed:.1f}s)")
        else:
            failed += 1
            print(f"FAIL     ({elapsed:.1f}s)  {err[:60]}")

        results.append({"id": tid, "category": cat, "has_code": True, "compiled": compiles, "reason": err if not compiles else "ok"})

    # Summary
    print("\n" + "=" * 70)
    print("  FULL COMPILATION RESULTS")
    print("=" * 70)
    print(f"  Total tasks:        {len(tasks)}")
    print(f"  Produced Rust code: {total_with_code}")
    print(f"  No Rust code:       {no_code} (explanations, TypeScript, etc.)")
    print(f"  Compiled:           {compiled}/{total_with_code}  ({compiled/total_with_code*100:.1f}%)" if total_with_code else "")
    print(f"  Failed:             {failed}/{total_with_code}" if total_with_code else "")
    print("=" * 70)

    # Per-category breakdown
    cat_stats = {}
    for r in results:
        c = r["category"]
        if c not in cat_stats:
            cat_stats[c] = {"total": 0, "has_code": 0, "compiled": 0}
        cat_stats[c]["total"] += 1
        if r["has_code"]:
            cat_stats[c]["has_code"] += 1
            if r["compiled"]:
                cat_stats[c]["compiled"] += 1

    print("\n  Category breakdown (only tasks with Rust code):")
    for cat in sorted(cat_stats):
        s = cat_stats[cat]
        if s["has_code"] > 0:
            pct = s["compiled"] / s["has_code"] * 100
            print(f"    {cat:30s}  {s['compiled']:2d}/{s['has_code']:2d}  ({pct:.0f}%)")

    # Failed tasks
    failed_tasks = [r for r in results if r["has_code"] and not r["compiled"]]
    if failed_tasks:
        print(f"\n  Failed compilations:")
        for r in failed_tasks:
            print(f"    {r['id']:16s}  {r['reason'][:80]}")

    # Save
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_tasks": len(tasks),
        "produced_code": total_with_code,
        "compiled": compiled,
        "failed": failed,
        "no_code": no_code,
        "compile_rate": round(compiled / total_with_code, 4) if total_with_code else 0,
        "results": results,
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"compile_full_{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {path}")


if __name__ == "__main__":
    main()
