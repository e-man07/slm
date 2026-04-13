#!/usr/bin/env python3
"""Fix training data on the container.

Reads existing cpt_train.jsonl and sft_train.jsonl, fixes:
1. CPT: Flatten JSON Q&A blobs into clean text
2. SFT: Remove placeholder stubs, license files; add proper Q&A ChatML pairs
3. Remove CC-BY-SA-4.0-no-training records

Usage:
    python /workspace/scripts/fix_training_data.py
    python /workspace/scripts/fix_training_data.py --data-dir /workspace/data
    python /workspace/scripts/fix_training_data.py --dry-run
"""

import json
import sys
from pathlib import Path

SYSTEM_PROMPT = (
    "You are an expert Solana and Anchor developer. "
    "Provide accurate, secure, and up-to-date code and guidance."
)

EXCLUDED_LICENSES = {"CC-BY-SA-4.0-no-training", "CC-BY-SA-4.0-anti-LLM"}


def try_parse_qa_json(text):
    """Try to parse text (possibly after stripping a comment prefix) as {question, answer}."""
    content = text
    # Strip HTML comment prefix added by record_to_cpt
    if content.startswith("<!--"):
        parts = content.split("\n\n", 1)
        if len(parts) == 2:
            content = parts[1]

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "question" in parsed and "answer" in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def try_parse_messages_json(text):
    """Try to parse text as [{role, content}, ...]."""
    content = text
    if content.startswith("<!--"):
        parts = content.split("\n\n", 1)
        if len(parts) == 2:
            content = parts[1]
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict) and "role" in parsed[0]:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def fix_cpt(data_dir, dry_run=False):
    """Fix CPT data: flatten JSON Q&A blobs into clean text."""
    cpt_path = data_dir / "cpt_train.jsonl"
    if not cpt_path.exists():
        print(f"ERROR: {cpt_path} not found")
        return

    print(f"Reading {cpt_path}...")
    fixed = []
    stats = {"json_qa_fixed": 0, "messages_fixed": 0, "license_removed": 0, "unchanged": 0}

    with open(cpt_path) as f:
        for line in f:
            rec = json.loads(line)
            text = rec["text"]

            # Check for excluded license in source comment
            source_line = text.split("\n")[0] if text.startswith("<!--") or text.startswith("//") else ""

            # Try to fix JSON Q&A blobs
            qa = try_parse_qa_json(text)
            if qa:
                q = qa["question"].strip()
                a = qa["answer"].strip()
                rec["text"] = f"Question: {q}\n\nAnswer: {a}"
                stats["json_qa_fixed"] += 1
            else:
                msgs = try_parse_messages_json(text)
                if msgs:
                    parts = []
                    for m in msgs:
                        role = m.get("role", "")
                        content = m.get("content", "")
                        if role == "system":
                            continue
                        elif role == "user":
                            parts.append(f"Question: {content}")
                        elif role == "assistant":
                            parts.append(f"Answer: {content}")
                    if parts:
                        rec["text"] = "\n\n".join(parts)
                        stats["messages_fixed"] += 1
                    else:
                        stats["unchanged"] += 1
                else:
                    stats["unchanged"] += 1

            fixed.append(rec)

    print(f"  JSON Q&A fixed: {stats['json_qa_fixed']:,}")
    print(f"  Messages fixed: {stats['messages_fixed']:,}")
    print(f"  Unchanged: {stats['unchanged']:,}")
    print(f"  Total: {len(fixed):,}")

    if not dry_run:
        out_path = data_dir / "cpt_train.jsonl"
        backup = data_dir / "cpt_train.jsonl.bak"
        print(f"  Backing up to {backup}...")
        cpt_path.rename(backup)
        print(f"  Writing fixed data to {out_path}...")
        with open(out_path, "w") as f:
            for rec in fixed:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  Done: {len(fixed):,} records written")


def fix_sft(data_dir, dry_run=False):
    """Fix SFT data: remove placeholders/junk, add Q&A ChatML pairs from CPT."""
    sft_path = data_dir / "sft_train.jsonl"
    cpt_path = data_dir / "cpt_train.jsonl"

    # First: clean existing SFT data
    clean_sft = []
    removed = {"placeholder": 0, "license": 0, "short": 0}

    if sft_path.exists():
        print(f"\nCleaning existing {sft_path}...")
        with open(sft_path) as f:
            for line in f:
                rec = json.loads(line)
                text = json.dumps(rec)
                if "would be filled by synthetic" in text:
                    removed["placeholder"] += 1
                    continue
                msgs = rec.get("messages", [])
                if msgs:
                    first_user = next((m["content"] for m in msgs if m["role"] == "user"), "")
                    if "MIT License" in first_user[:100] or "Apache License" in first_user[:100] or "Permission is hereby granted" in first_user[:200]:
                        removed["license"] += 1
                        continue
                    assistant_text = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
                    if len(assistant_text) < 20:
                        removed["short"] += 1
                        continue
                clean_sft.append(rec)
        print(f"  Kept: {len(clean_sft):,}")
        print(f"  Removed placeholders: {removed['placeholder']:,}")
        print(f"  Removed license files: {removed['license']:,}")
        print(f"  Removed short: {removed['short']:,}")

    # Second: generate new SFT pairs from the fixed CPT Q&A data
    print(f"\nGenerating SFT pairs from CPT Q&A data...")
    new_sft = 0
    if cpt_path.exists():
        with open(cpt_path) as f:
            for line in f:
                rec = json.loads(line)
                text = rec["text"]
                if text.startswith("Question: ") and "\n\nAnswer: " in text:
                    parts = text.split("\n\nAnswer: ", 1)
                    q = parts[0].replace("Question: ", "", 1).strip()
                    a = parts[1].strip()
                    if len(a) >= 20 and len(q) >= 10:
                        sft_rec = {
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": q},
                                {"role": "assistant", "content": a},
                            ]
                        }
                        clean_sft.append(sft_rec)
                        new_sft += 1

    print(f"  New SFT pairs from Q&A: {new_sft:,}")
    print(f"  Total SFT records: {len(clean_sft):,}")

    if not dry_run:
        backup = data_dir / "sft_train.jsonl.bak"
        if sft_path.exists():
            print(f"  Backing up to {backup}...")
            sft_path.rename(backup)
        print(f"  Writing fixed SFT data...")
        with open(sft_path, "w") as f:
            for rec in clean_sft:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  Done: {len(clean_sft):,} records written")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fix training data")
    parser.add_argument("--data-dir", default="/workspace/data", help="Data directory")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without modifying files")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Data directory: {data_dir}")
    print(f"Dry run: {args.dry_run}\n")

    fix_cpt(data_dir, args.dry_run)
    fix_sft(data_dir, args.dry_run)

    print("\nAll done!")


if __name__ == "__main__":
    main()
