#!/usr/bin/env python3
"""Curate high-quality subsets from sft_train.jsonl for progressive training.

Creates:
- sft_10k.jsonl  (Phase 1: validation run)
- sft_50k.jsonl  (Phase 2: main training)

Prioritizes: Solana-specific content, modern Anchor patterns, migration examples,
diverse task categories. Deprioritizes: generic Rust, non-Solana Q&A.
"""
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "final"

SOLANA_KEYWORDS = [
    "solana", "anchor", "spl", "token", "pda", "program", "account",
    "instruction", "transaction", "wallet", "keypair", "pubkey",
    "lamport", "rent", "cpi", "cross-program", "metaplex", "nft",
    "declare_program", "initspace", "ctx.bumps", "anchor_lang",
    "anchor_spl", "system_program", "token_program",
]

MODERN_ANCHOR_KEYWORDS = [
    "declare_program!", "InitSpace", "ctx.bumps", "#[account(init",
    "#[account(seeds", "anchor 0.30", "solana-foundation/anchor",
    "require!(", "require_keys_eq!", "#[derive(Accounts)]",
]

MIGRATION_KEYWORDS = [
    "migrate", "migration", "old pattern", "modern pattern",
    "declare_id!", "coral-xyz", "deprecated",
]


def score_record(rec):
    """Score a record by quality/relevance. Higher = better."""
    text = json.dumps(rec).lower()
    score = 0

    # Solana relevance
    solana_hits = sum(1 for kw in SOLANA_KEYWORDS if kw.lower() in text)
    score += solana_hits * 10

    # Modern Anchor patterns (highest value)
    modern_hits = sum(1 for kw in MODERN_ANCHOR_KEYWORDS if kw.lower() in text)
    score += modern_hits * 25

    # Migration examples (very high value)
    migration_hits = sum(1 for kw in MIGRATION_KEYWORDS if kw.lower() in text)
    score += migration_hits * 30

    # Has actual code (rust blocks)
    if "```rust" in text or "fn " in text or "pub struct" in text:
        score += 20

    # Has good Q&A structure (system + user + assistant)
    msgs = rec.get("messages", [])
    if len(msgs) == 3:
        assistant = msgs[-1].get("content", "")
        if len(assistant) > 100:
            score += 10  # Good length answer
        if len(assistant) > 500:
            score += 10  # Detailed answer

    # Penalize very short answers
    if msgs and len(msgs[-1].get("content", "")) < 50:
        score -= 20

    # Penalize non-Solana content
    if solana_hits == 0:
        score -= 15

    return score


def main():
    sft_path = DATA_DIR / "sft_train.jsonl"
    if not sft_path.exists():
        print(f"ERROR: {sft_path} not found")
        return

    print(f"Loading {sft_path}...")
    records = []
    with open(sft_path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"  Loaded {len(records):,} records")

    # Score all records
    print("Scoring records...")
    scored = [(score_record(r), i, r) for i, r in enumerate(records)]
    scored.sort(key=lambda x: -x[0])  # highest score first

    # Show score distribution
    scores = [s for s, _, _ in scored]
    print(f"  Score range: {min(scores)} to {max(scores)}")
    print(f"  Median score: {scores[len(scores)//2]}")
    print(f"  Records with score > 50: {sum(1 for s in scores if s > 50):,}")
    print(f"  Records with score > 100: {sum(1 for s in scores if s > 100):,}")

    # Create 10K subset (top scored, then shuffle for training)
    top_10k = [r for _, _, r in scored[:10000]]
    random.seed(42)
    random.shuffle(top_10k)

    out_10k = DATA_DIR / "sft_10k.jsonl"
    with open(out_10k, "w") as f:
        for r in top_10k:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  sft_10k.jsonl: {len(top_10k):,} records -> {out_10k}")

    # Create 50K subset
    top_50k = [r for _, _, r in scored[:50000]]
    random.shuffle(top_50k)

    out_50k = DATA_DIR / "sft_50k.jsonl"
    with open(out_50k, "w") as f:
        for r in top_50k:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  sft_50k.jsonl: {len(top_50k):,} records -> {out_50k}")

    # Show what's in the 10K subset
    print("\n  10K subset composition:")
    solana_count = sum(1 for r in top_10k if any(
        kw in json.dumps(r).lower() for kw in ["solana", "anchor", "spl"]
    ))
    code_count = sum(1 for r in top_10k if "```rust" in json.dumps(r) or "fn " in json.dumps(r))
    migration_count = sum(1 for r in top_10k if any(
        kw in json.dumps(r).lower() for kw in MIGRATION_KEYWORDS
    ))
    print(f"    Solana-related: {solana_count:,}")
    print(f"    Contains code: {code_count:,}")
    print(f"    Migration examples: {migration_count}")

    print("\nDone!")


if __name__ == "__main__":
    main()
