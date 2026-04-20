#!/usr/bin/env python3
"""Sealevel Compilation Benchmark — tests if model-generated Anchor code actually compiles.

Sends coding prompts to the API, extracts Rust code from responses,
writes it into an Anchor project, and runs `cargo check`.

Usage:
    python training/eval_compile.py \
        --api-url http://HOST/v1 \
        --api-key sk-... \
        --output-dir results/compile-eval
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

_patterns = (Path(__file__).parent.parent / "deploy" / "rag-api" / "anchor_patterns.md").read_text()

SYSTEM_PROMPT = f"""You are Sealevel, an expert Solana and Anchor 0.32 development assistant.
Write complete, compilable Anchor Rust code. Output ONLY Rust code inside a ```rust block.
The program module MUST be named `bench_project`.

Use these verified compilable patterns as reference:

{_patterns}

IMPORTANT:
- Always include `use anchor_lang::prelude::*;` and `declare_id!("11111111111111111111111111111111");`
- For SOL transfers use `anchor_lang::system_program::{{transfer, Transfer}}`
- For has_one, field names must match exactly between Account struct and Accounts struct
- Use `#[instruction(arg: Type)]` when seeds reference instruction arguments
- Read fields into local variables before mutating to avoid borrow conflicts
- Use checked arithmetic for user values
"""

# 20 coding tasks that should produce compilable Anchor code
COMPILE_TASKS = [
    {
        "id": "comp-01",
        "prompt": "Write a complete Anchor program with an `initialize` instruction that creates a new account storing a u64 counter initialized to 0. Include the account struct with space calculation.",
        "description": "Basic account creation with counter",
    },
    {
        "id": "comp-02",
        "prompt": "Write a complete Anchor program with an `increment` instruction that increments a counter stored in a PDA account. The PDA should use seeds=[b\"counter\", user.key().as_ref()].",
        "description": "PDA counter increment",
    },
    {
        "id": "comp-03",
        "prompt": "Write a complete Anchor program with a `transfer_sol` instruction that transfers SOL from the signer to a recipient using the system program CPI.",
        "description": "SOL transfer via system program CPI",
    },
    {
        "id": "comp-04",
        "prompt": "Write a complete Anchor program with custom error codes using #[error_code]. Include at least 3 error variants and a `validate` instruction that uses require! macro.",
        "description": "Custom errors with require!",
    },
    {
        "id": "comp-05",
        "prompt": "Write a complete Anchor program with an `initialize_vault` instruction that creates a vault PDA account storing an authority pubkey and a balance (u64). Use InitSpace derive.",
        "description": "Vault with InitSpace",
    },
    {
        "id": "comp-06",
        "prompt": "Write a complete Anchor program with a `deposit` instruction that increments a vault's balance field. Validate the signer matches the vault's authority using has_one constraint.",
        "description": "Deposit with has_one constraint",
    },
    {
        "id": "comp-07",
        "prompt": "Write a complete Anchor program with a `close_account` instruction that closes a data account and sends the lamports back to the signer using the close constraint.",
        "description": "Account closing",
    },
    {
        "id": "comp-08",
        "prompt": "Write a complete Anchor program with an `update_data` instruction that updates a String field in an account. The String should have a max length of 200 chars. Use constraint to validate signer is authority.",
        "description": "String data update with constraint",
    },
    {
        "id": "comp-09",
        "prompt": "Write a complete Anchor program with an `emit_event` instruction that emits a custom event using #[event] and emit! macro. The event should contain a pubkey, amount (u64), and timestamp (i64).",
        "description": "Event emission",
    },
    {
        "id": "comp-10",
        "prompt": "Write a complete Anchor program with a `create_profile` instruction. The profile account is a PDA with seeds=[b\"profile\", user.key().as_ref()] and stores name (String max 50) and score (u64).",
        "description": "Profile PDA creation",
    },
    {
        "id": "comp-11",
        "prompt": "Write a complete Anchor program with two instructions: `register` (creates a user account with name and points=0) and `add_points` (increments points by a given amount). Use checked_add for safety.",
        "description": "Two instructions with checked math",
    },
    {
        "id": "comp-12",
        "prompt": "Write a complete Anchor program with a `set_config` instruction that can only be called by a hardcoded admin pubkey. Store a fee_rate (u16) and is_paused (bool) in a config PDA with seeds=[b\"config\"].",
        "description": "Admin-only config with hardcoded key",
    },
    {
        "id": "comp-13",
        "prompt": "Write a complete Anchor program with a `create_listing` instruction for a marketplace. The listing PDA uses seeds=[b\"listing\", seller.key().as_ref(), &price.to_le_bytes()]. Store seller, price (u64), and is_active (bool).",
        "description": "Marketplace listing PDA",
    },
    {
        "id": "comp-14",
        "prompt": "Write a complete Anchor program with a `withdraw` instruction that checks the current Clock timestamp against an unlock_time stored in the account. Only allow withdrawal if current time >= unlock_time.",
        "description": "Time-locked withdrawal",
    },
    {
        "id": "comp-15",
        "prompt": "Write a complete Anchor program with a `vote` instruction. A proposal account stores yes_votes and no_votes (both u64). The vote instruction takes a bool parameter and increments the appropriate counter.",
        "description": "Voting with bool parameter",
    },
    {
        "id": "comp-16",
        "prompt": "Write a complete Anchor program with an `initialize_multisig` instruction that stores 3 signer pubkeys and a threshold (u8) in an account. Use InitSpace.",
        "description": "Multisig initialization",
    },
    {
        "id": "comp-17",
        "prompt": "Write a complete Anchor program with `create_escrow` and `release_escrow` instructions. The escrow PDA stores sender, receiver, amount, and is_released (bool). release_escrow validates the signer is the sender.",
        "description": "Escrow create and release",
    },
    {
        "id": "comp-18",
        "prompt": "Write a complete Anchor program with a `record_score` instruction that stores a game score. The account stores player (Pubkey), score (u64), and timestamp (i64 from Clock sysvar).",
        "description": "Game score recording with Clock",
    },
    {
        "id": "comp-19",
        "prompt": "Write a complete Anchor program with a `batch_update` instruction that takes a Vec<u64> parameter and stores its sum in an account. Use checked arithmetic.",
        "description": "Vec parameter with sum",
    },
    {
        "id": "comp-20",
        "prompt": "Write a complete Anchor program with an `init_registry` instruction that creates a registry PDA (seeds=[b\"registry\"]) storing an entries_count (u32) and authority (Pubkey), and an `add_entry` instruction that increments entries_count. Validate authority with has_one.",
        "description": "Registry with add_entry",
    },
]


def extract_rust_code(response: str) -> str | None:
    """Extract Rust code from a markdown response."""
    # Try ```rust ... ``` blocks first
    matches = re.findall(r'```rust\s*\n(.*?)```', response, re.DOTALL)
    if matches:
        # Return the longest match (most likely the full program)
        return max(matches, key=len).strip()

    # Try ``` ... ``` blocks
    matches = re.findall(r'```\s*\n(.*?)```', response, re.DOTALL)
    if matches:
        code = max(matches, key=len).strip()
        if 'anchor_lang' in code or '#[program]' in code:
            return code

    return None


def fixup_code(code: str) -> str:
    """Auto-fix common boilerplate issues that aren't logic errors."""
    # Add declare_id! if no program ID declaration exists
    if 'declare_id!' not in code and 'declare_program!' not in code:
        code = 'declare_id!("11111111111111111111111111111111");\n\n' + code
    # Ensure anchor_lang prelude is imported
    if 'use anchor_lang::prelude::*' not in code:
        code = 'use anchor_lang::prelude::*;\n' + code
    return code


def check_compiles(code: str, project_dir: str) -> tuple[bool, str]:
    """Write code to the Anchor project and run cargo check."""
    code = fixup_code(code)
    lib_path = Path(project_dir) / "programs" / "bench_project" / "src" / "lib.rs"
    lib_path.write_text(code)

    result = subprocess.run(
        ["cargo", "check", "--manifest-path",
         str(Path(project_dir) / "programs" / "bench_project" / "Cargo.toml")],
        capture_output=True, text=True, timeout=120
    )

    if result.returncode == 0:
        return True, "Compiles successfully"
    else:
        # Extract first error
        errors = [l for l in result.stderr.split('\n') if 'error[' in l or 'error:' in l]
        first_error = errors[0][:150] if errors else result.stderr[:150]
        return False, first_error


def generate_via_api(client, api_url, api_key, prompt, model="slm-solana", max_tokens=1024):
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


def main():
    parser = argparse.ArgumentParser(description="Sealevel Compilation Benchmark")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="slm-solana")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--project-dir", default="/tmp/slm-bench/bench_project")
    parser.add_argument("--output-dir", default="results/compile-eval")
    args = parser.parse_args()

    print("=" * 60)
    print("  Sealevel — Compilation Benchmark")
    print("=" * 60)
    print(f"  Endpoint:  {args.api_url}")
    print(f"  Tasks:     {len(COMPILE_TASKS)}")
    print(f"  Project:   {args.project_dir}")
    print("=" * 60)

    client = httpx.Client()
    results = []
    passed = 0

    for i, task in enumerate(COMPILE_TASKS):
        tid = task["id"]
        print(f"  [{i+1:2d}/{len(COMPILE_TASKS)}] {tid:10s} {task['description']:40s} ", end="", flush=True)

        t0 = time.time()

        # Get model response
        try:
            response = generate_via_api(
                client, args.api_url, args.api_key, task["prompt"],
                model=args.model, max_tokens=args.max_tokens,
            )
        except Exception as e:
            elapsed = time.time() - t0
            print(f"API_ERR  ({elapsed:.1f}s)")
            results.append({"id": tid, "passed": False, "reason": f"API error: {e}",
                            "code": "", "response_preview": "", "elapsed_s": round(elapsed, 2)})
            continue

        # Extract code
        code = extract_rust_code(response)
        if not code:
            elapsed = time.time() - t0
            print(f"NO_CODE  ({elapsed:.1f}s)")
            results.append({"id": tid, "passed": False, "reason": "No Rust code block found",
                            "code": "", "response_preview": response[:200], "elapsed_s": round(elapsed, 2)})
            continue

        # Try compilation
        try:
            compiles, msg = check_compiles(code, args.project_dir)
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"TIMEOUT  ({elapsed:.1f}s)")
            results.append({"id": tid, "passed": False, "reason": "Compilation timeout",
                            "code": code[:500], "response_preview": "", "elapsed_s": round(elapsed, 2)})
            continue

        elapsed = time.time() - t0

        if compiles:
            passed += 1
            print(f"PASS     ({elapsed:.1f}s)")
        else:
            print(f"FAIL     ({elapsed:.1f}s)  {msg[:80]}")

        results.append({
            "id": tid,
            "description": task["description"],
            "passed": compiles,
            "reason": msg,
            "code": code[:1000],
            "elapsed_s": round(elapsed, 2),
        })

    # Summary
    total = len(COMPILE_TASKS)
    score = passed / total if total > 0 else 0

    print("\n" + "=" * 60)
    print(f"  COMPILATION BENCHMARK RESULTS")
    print("=" * 60)
    bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
    print(f"  Compiled:  {passed}/{total}  [{bar}] {score:.1%}")
    print("=" * 60)

    # Failed tasks
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n  Failed tasks:")
        for r in failed:
            print(f"    {r['id']}: {r['reason'][:100]}")

    # Save report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_url": args.api_url,
        "model": args.model,
        "compiled": passed,
        "total": total,
        "score": round(score, 4),
        "results": results,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"compile_eval_{ts}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
