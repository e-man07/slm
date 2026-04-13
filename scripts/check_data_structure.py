#!/usr/bin/env python3
"""Check data structure consistency across all training files."""
import json
from pathlib import Path

DATA_DIR = Path("/workspace/data")

# === CPT ===
print("=== CPT FORMAT CHECK ===")
has_text = 0
extra_keys = set()
bad = 0
samples = {}
with open(DATA_DIR / "cpt_train.jsonl") as f:
    for line in f:
        rec = json.loads(line)
        keys = set(rec.keys())
        if "text" in keys:
            has_text += 1
        if keys != {"text"}:
            extra_keys.update(keys - {"text"})
            bad += 1
        text = rec.get("text", "")
        if "Strandset" in text and "strandset" not in samples:
            samples["strandset"] = text[:200]
        elif text.startswith("Question:") and "qa" not in samples:
            samples["qa"] = text[:200]
        elif text.startswith("//") and "code" not in samples:
            samples["code"] = text[:200]

print(f"  Total with 'text' key: {has_text:,}")
print(f"  Extra keys: {extra_keys or 'none'}")
print(f"  Records with extra keys: {bad}")
for k, v in samples.items():
    print(f"\n  Sample ({k}):\n    {v}")

# === SFT ===
print("\n=== SFT FORMAT CHECK ===")
has_messages = 0
has_text_only = 0
missing_system = 0
missing_assistant = 0
role_combos = {}
with open(DATA_DIR / "sft_train.jsonl") as f:
    for line in f:
        rec = json.loads(line)
        if "messages" in rec:
            has_messages += 1
            msgs = rec["messages"]
            roles = tuple(m.get("role") for m in msgs)
            role_combos[roles] = role_combos.get(roles, 0) + 1
            if not msgs or msgs[0].get("role") != "system":
                missing_system += 1
            if "assistant" not in [m.get("role") for m in msgs]:
                missing_assistant += 1
        elif "text" in rec:
            has_text_only += 1

print(f"  With 'messages': {has_messages:,}")
print(f"  With 'text' only: {has_text_only}")
print(f"  Missing system prompt: {missing_system}")
print(f"  Missing assistant: {missing_assistant}")
print(f"  Role patterns (top 5):")
for roles, count in sorted(role_combos.items(), key=lambda x: -x[1])[:5]:
    print(f"    {roles}: {count:,}")

# === DPO ===
print("\n=== DPO FORMAT CHECK ===")
for fpath in sorted(DATA_DIR.glob("dpo-*.jsonl")):
    with open(fpath) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    if lines:
        keys = set().union(*[set(r.keys()) for r in lines])
        print(f"  {fpath.name}: {len(lines)} records, keys={keys}")
        # Check first record
        first = lines[0]
        content = first.get("content", first.get("messages", ""))
        print(f"    Sample: {str(content)[:150]}")
    else:
        print(f"  {fpath.name}: EMPTY")
