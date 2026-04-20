#!/usr/bin/env python3
"""Sealevel Compilation Benchmark with self-correction retry loop.

Generate → compile → if fail, feed error back → retry (up to N times).
"""
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

from eval_compile import COMPILE_TASKS, SYSTEM_PROMPT, extract_rust_code, fixup_code

RETRY_PROMPT = (
    "The code you wrote does not compile. Here is the compiler error:\n\n"
    "```\n{error}\n```\n\n"
    "Please fix the code. Output ONLY the complete corrected Rust code inside a ```rust block. "
    "Do not explain, just output the fixed code."
)


def generate(client, api_url, api_key, messages, model="slm-solana", max_tokens=1024):
    resp = client.post(
        f"{api_url}/chat/completions",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": messages,
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
    errors = result.stderr
    # Extract just error lines (not warnings)
    error_lines = [l for l in errors.split('\n') if 'error' in l.lower()]
    return False, '\n'.join(error_lines[:10])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="slm-solana")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--project-dir", default="/tmp/slm-bench/bench_project")
    parser.add_argument("--output-dir", default="results/compile-eval")
    args = parser.parse_args()

    print("=" * 64)
    print("  Sealevel — Compilation Benchmark (with self-correction)")
    print("=" * 64)
    print(f"  Endpoint:    {args.api_url}")
    print(f"  Max retries: {args.max_retries}")
    print(f"  Tasks:       {len(COMPILE_TASKS)}")
    print("=" * 64)

    client = httpx.Client()
    results = []
    first_try_pass = 0
    final_pass = 0

    for i, task in enumerate(COMPILE_TASKS):
        tid = task["id"]
        desc = task["description"]
        print(f"\n  [{i+1:2d}/{len(COMPILE_TASKS)}] {tid} — {desc}")

        t0 = time.time()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": task["prompt"]},
        ]

        passed = False
        attempts = 0

        for attempt in range(1 + args.max_retries):
            attempts = attempt + 1

            # Generate
            try:
                response = generate(client, args.api_url, args.api_key, messages, args.model)
            except Exception as e:
                print(f"    Attempt {attempts}: API_ERR — {e}")
                break

            # Extract code
            code = extract_rust_code(response)
            if not code:
                print(f"    Attempt {attempts}: NO_CODE")
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": "Please output the complete Rust code inside a ```rust code block."})
                continue

            # Compile
            try:
                compiles, error_msg = try_compile(code, args.project_dir)
            except subprocess.TimeoutExpired:
                print(f"    Attempt {attempts}: TIMEOUT")
                break

            if compiles:
                passed = True
                if attempt == 0:
                    first_try_pass += 1
                    print(f"    Attempt {attempts}: PASS (first try)")
                else:
                    print(f"    Attempt {attempts}: PASS (fixed after {attempt} retries)")
                break
            else:
                short_err = error_msg.split('\n')[0][:80]
                print(f"    Attempt {attempts}: FAIL — {short_err}")
                # Feed error back for retry
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": RETRY_PROMPT.format(error=error_msg)})

        elapsed = time.time() - t0
        if passed:
            final_pass += 1

        results.append({
            "id": tid,
            "description": desc,
            "passed": passed,
            "attempts": attempts,
            "elapsed_s": round(elapsed, 2),
        })

    # Summary
    total = len(COMPILE_TASKS)
    first_score = first_try_pass / total
    final_score = final_pass / total

    print("\n" + "=" * 64)
    print("  COMPILATION BENCHMARK — SELF-CORRECTION RESULTS")
    print("=" * 64)
    bar1 = "#" * int(first_score * 20) + "." * (20 - int(first_score * 20))
    bar2 = "#" * int(final_score * 20) + "." * (20 - int(final_score * 20))
    print(f"  First try:   {first_try_pass:2d}/{total}  [{bar1}] {first_score:.1%}")
    print(f"  After retry: {final_pass:2d}/{total}  [{bar2}] {final_score:.1%}")
    print(f"  Improvement: +{final_pass - first_try_pass} tasks fixed via self-correction")
    print("=" * 64)

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n  Still failed after {args.max_retries} retries:")
        for r in failed:
            print(f"    {r['id']}: {r['description']}")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "max_retries": args.max_retries,
        "first_try": {"passed": first_try_pass, "total": total, "score": round(first_score, 4)},
        "after_retry": {"passed": final_pass, "total": total, "score": round(final_score, 4)},
        "results": results,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"compile_retry_{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {path}")


if __name__ == "__main__":
    main()
