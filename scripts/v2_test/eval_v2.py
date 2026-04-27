"""V2 evaluation: run the 80-task Solana benchmark on the v2 adapter.

Differences from training/eval.py:
  1. Loads BASE model + v2 LoRA adapter via PeftModel.from_pretrained
     (production eval.py treats model_path as a full merged model)
  2. Applies clean_model_response + fix_anchor_code post-processing to outputs
     BEFORE scoring (matches what production CLI/web does)
  3. Reports both raw and cleaned scores so we can see how much the cleaner helps

Run on H100 (sealevel must be pip-installed for parser/post-processing):
    python scripts/v2_test/eval_v2.py \
        --base-model unsloth/qwen2.5-coder-7b-instruct-bnb-4bit \
        --adapter WhyParabola/sealevel-solana-lora-v2 \
        --tasks-file /workspace/training/eval_tasks.json \
        --report-out /workspace/eval_v2_report.json
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
from datetime import datetime, timezone
from pathlib import Path

os.environ["TRANSFORMERS_ATTENTION_IMPLEMENTATION"] = "eager"

import torch
from peft import PeftModel
from unsloth import FastLanguageModel

# Use canonical post-processing from sealevel CLI (pip install sealevel)
from sealevel_cli.client import clean_model_response, fix_anchor_code

# Reuse the production eval scoring logic
sys.path.insert(0, str(Path("/workspace/training")))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "training"))
from eval import EVAL_TASKS, SYSTEM_PROMPT, score_task  # noqa: E402


def generate_response(model, tokenizer, prompt: str, max_new_tokens: int = 512, temperature: float = 0.0) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature if temperature > 0 else None,
            do_sample=temperature > 0,
            use_cache=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def post_process(raw: str) -> str:
    """Apply production-grade cleaning the same way the CLI does."""
    return fix_anchor_code(clean_model_response(raw))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default="unsloth/qwen2.5-coder-7b-instruct-bnb-4bit")
    parser.add_argument("--adapter", default="WhyParabola/sealevel-solana-lora-v2")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-seq-length", type=int, default=8192)
    parser.add_argument("--report-out", type=Path, default=Path("/workspace/eval_v2_report.json"))
    parser.add_argument("--limit", type=int, default=None, help="Run only N tasks (debug)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"  Sealevel v2 — 80-task Solana eval with post-processing")
    print("=" * 70)
    print(f"  Base:    {args.base_model}")
    print(f"  Adapter: {args.adapter}")
    print(f"  Tasks:   {len(EVAL_TASKS)}")
    print()

    # ── Load base + adapter ──
    print("[1/3] Loading base model...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
        attn_implementation="eager",
    )
    print(f"[1/3] Loading v2 adapter: {args.adapter}")
    model = PeftModel.from_pretrained(model, args.adapter)
    FastLanguageModel.for_inference(model)
    if hasattr(model, "config"):
        model.config._attn_implementation = "eager"
    print("  Loaded.\n")

    # ── Run eval ──
    tasks = EVAL_TASKS if args.limit is None else EVAL_TASKS[:args.limit]
    print(f"[2/3] Running {len(tasks)} tasks (raw + post-processed scoring)...")
    results = []
    cat_raw: dict[str, dict] = {}
    cat_clean: dict[str, dict] = {}

    for i, task in enumerate(tasks):
        t0 = time.time()
        raw = generate_response(model, tokenizer, task["prompt"], args.max_new_tokens, args.temperature)
        elapsed = time.time() - t0

        cleaned = post_process(raw)

        # Score both versions
        raw_result = score_task(task, raw)
        clean_result = score_task(task, cleaned)

        results.append({
            "id": task["id"],
            "category": task["category"],
            "raw_passed": raw_result["passed"],
            "raw_reason": raw_result["reason"],
            "clean_passed": clean_result["passed"],
            "clean_reason": clean_result["reason"],
            "elapsed_s": round(elapsed, 2),
            "raw_preview": raw[:200],
            "clean_preview": cleaned[:200],
        })

        c = task["category"]
        cat_raw.setdefault(c, {"total": 0, "passed": 0})
        cat_clean.setdefault(c, {"total": 0, "passed": 0})
        cat_raw[c]["total"] += 1
        cat_clean[c]["total"] += 1
        if raw_result["passed"]:
            cat_raw[c]["passed"] += 1
        if clean_result["passed"]:
            cat_clean[c]["passed"] += 1

        raw_status = "PASS" if raw_result["passed"] else "FAIL"
        clean_status = "PASS" if clean_result["passed"] else "FAIL"
        bonus = " (+CLEAN)" if clean_result["passed"] and not raw_result["passed"] else ""
        print(f"  [{i+1:3d}/{len(tasks)}] {task['id']:14s}  raw={raw_status} clean={clean_status}{bonus}  ({elapsed:.1f}s)")

    # ── Aggregate ──
    print(f"\n[3/3] Results")
    raw_passed = sum(1 for r in results if r["raw_passed"])
    clean_passed = sum(1 for r in results if r["clean_passed"])
    total = len(results)

    raw_score = raw_passed / total if total else 0
    clean_score = clean_passed / total if total else 0

    print(f"\n  Overall:  raw={raw_passed}/{total} ({raw_score:.1%})   cleaned={clean_passed}/{total} ({clean_score:.1%})")
    print(f"  Boost from post-processing: +{clean_passed - raw_passed} task(s)")

    print("\n  Per-category (raw vs cleaned):")
    for cat in sorted(set(list(cat_raw.keys()) + list(cat_clean.keys()))):
        rs = cat_raw.get(cat, {"passed": 0, "total": 0})
        cs = cat_clean.get(cat, {"passed": 0, "total": 0})
        rs_pct = rs["passed"] / rs["total"] if rs["total"] else 0
        cs_pct = cs["passed"] / cs["total"] if cs["total"] else 0
        boost = cs["passed"] - rs["passed"]
        boost_str = f"+{boost}" if boost > 0 else str(boost)
        print(f"    {cat:30s}  raw={rs['passed']:2d}/{rs['total']:2d} ({rs_pct:.0%})   "
              f"cleaned={cs['passed']:2d}/{cs['total']:2d} ({cs_pct:.0%})   [{boost_str}]")

    # Write JSON report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "adapter": args.adapter,
        "base_model": args.base_model,
        "totals": {
            "raw": {"passed": raw_passed, "total": total, "score": round(raw_score, 4)},
            "cleaned": {"passed": clean_passed, "total": total, "score": round(clean_score, 4)},
            "boost_from_cleaning": clean_passed - raw_passed,
        },
        "categories": {
            cat: {
                "raw": cat_raw.get(cat, {}),
                "cleaned": cat_clean.get(cat, {}),
            }
            for cat in sorted(set(list(cat_raw.keys()) + list(cat_clean.keys())))
        },
        "tasks": results,
    }
    args.report_out.write_text(json.dumps(report, indent=2))
    print(f"\n  Report saved to: {args.report_out}")


if __name__ == "__main__":
    main()
