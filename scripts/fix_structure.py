#!/usr/bin/env python3
"""Fix structural issues in training data:
1. CPT: Fix Strandset records that have raw dict strings instead of code
2. DPO: Unify schema across all chosen/rejected files
"""
import json
from pathlib import Path

DATA_DIR = Path("/workspace/data")

# === Fix CPT Strandset records with raw dict strings ===
print("=== Fixing CPT Strandset records ===")
cpt_path = DATA_DIR / "cpt_train.jsonl"
fixed_lines = []
strandset_fixed = 0
total = 0

with open(cpt_path) as f:
    for line in f:
        total += 1
        rec = json.loads(line)
        text = rec["text"]

        # Detect raw dict strings from Strandset (start with // Source: Strandset then have {'code':)
        if "Strandset-Rust-v1" in text and "{'code':" in text:
            # Extract the dict string after the source comment
            parts = text.split("\n\n", 1)
            if len(parts) == 2:
                prefix = parts[0]  # // Source: Strandset-Rust-v1 (category)
                dict_str = parts[1]
                try:
                    # Python dict literal — use ast.literal_eval
                    import ast
                    data = ast.literal_eval(dict_str)
                    if isinstance(data, dict) and "code" in data:
                        code = data["code"]
                        context = data.get("code_context", "")
                        if context:
                            rec["text"] = prefix + "\n\n" + context.strip() + "\n\n" + code.strip()
                        else:
                            rec["text"] = prefix + "\n\n" + code.strip()
                        strandset_fixed += 1
                except (ValueError, SyntaxError):
                    pass  # keep as-is if can't parse

        fixed_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"  Total: {total:,}")
print(f"  Strandset dict strings fixed: {strandset_fixed:,}")

with open(cpt_path, "w") as f:
    f.writelines(fixed_lines)
print(f"  Written: {len(fixed_lines):,} records")

# === Unify DPO format ===
print("\n=== Unifying DPO format ===")
for direction in ["chosen", "rejected"]:
    all_records = []
    for fpath in sorted(DATA_DIR.glob(f"dpo-{direction}*.jsonl")):
        with open(fpath) as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                # Extract content (messages JSON string) regardless of schema
                content = rec.get("content", "")
                if not content:
                    # Try to build from other fields
                    continue
                all_records.append({"content": content})

    out_path = DATA_DIR / f"dpo_{direction}.jsonl"
    with open(out_path, "w") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"  dpo_{direction}.jsonl: {len(all_records)} records (unified)")

print("\nDone!")
