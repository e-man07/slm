#!/usr/bin/env python3
"""Add new datasets and fix remaining data issues. v2 — fixed column parsing."""

import json
import sys
from pathlib import Path

SYSTEM_PROMPT = (
    "You are an expert Solana and Anchor developer. "
    "Provide accurate, secure, and up-to-date code and guidance."
)

DATA_DIR = Path("/workspace/data")


def remove_ccbysa():
    """Remove CC-BY-SA-4.0-no-training records."""
    print("\n=== Removing CC-BY-SA-4.0-no-training records ===")
    for fname in ["cpt_train.jsonl", "sft_train.jsonl"]:
        path = DATA_DIR / fname
        if not path.exists():
            continue
        kept = []
        removed = 0
        with open(path) as f:
            for line in f:
                if "CC-BY-SA-4.0" in line:
                    removed += 1
                else:
                    kept.append(line)
        if removed > 0:
            with open(path, "w") as f:
                f.writelines(kept)
        print(f"  {fname}: removed {removed}, kept {len(kept):,}")


def add_strandset_rust():
    """Download Strandset-Rust-v1 and convert to CPT + SFT."""
    print("\n=== Adding Strandset-Rust-v1 (191K Rust, Apache-2.0) ===")
    from datasets import load_dataset

    ds = load_dataset("Fortytwo-Network/Strandset-Rust-v1", split="train")
    print(f"  Downloaded {len(ds):,} examples")
    print(f"  Task categories: {set(row['task_category'] for row in ds.select(range(min(100, len(ds)))))}")

    cpt_records = []
    sft_records = []

    for row in ds:
        category = row.get("task_category", "")
        input_data = row.get("input_data", {})
        output_data = row.get("output_data", {})

        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except (json.JSONDecodeError, TypeError):
                input_data = {"code": input_data}
        if isinstance(output_data, str):
            try:
                output_data = json.loads(output_data)
            except (json.JSONDecodeError, TypeError):
                output_data = {"text": output_data}

        code = input_data.get("code", "") if isinstance(input_data, dict) else str(input_data)
        if not code or len(code.strip()) < 30:
            continue

        # Build a meaningful Q&A pair based on the task category
        if category == "comment_generation":
            commented = output_data.get("commented_code", "") if isinstance(output_data, dict) else str(output_data)
            if commented:
                question = f"Add clear comments to this Rust code:\n\n```rust\n{code.strip()}\n```"
                answer = f"Here's the commented version:\n\n```rust\n{commented.strip()}\n```"
            else:
                continue
        elif category == "code_explanation":
            explanation = output_data.get("explanation", output_data.get("text", "")) if isinstance(output_data, dict) else str(output_data)
            if explanation:
                question = f"Explain this Rust code:\n\n```rust\n{code.strip()}\n```"
                answer = explanation.strip()
            else:
                continue
        elif category == "code_completion":
            completion = output_data.get("completed_code", output_data.get("code", "")) if isinstance(output_data, dict) else str(output_data)
            if completion:
                question = f"Complete this Rust code:\n\n```rust\n{code.strip()}\n```"
                answer = f"```rust\n{completion.strip()}\n```"
            else:
                continue
        elif category == "bug_detection":
            bugs = output_data.get("bugs", output_data.get("text", "")) if isinstance(output_data, dict) else str(output_data)
            if bugs:
                question = f"Find bugs in this Rust code:\n\n```rust\n{code.strip()}\n```"
                answer = str(bugs).strip()
            else:
                continue
        else:
            # Generic: use code as CPT only
            out_text = str(output_data) if output_data else ""
            if out_text and len(out_text) > 30:
                question = f"Analyze this Rust code:\n\n```rust\n{code.strip()}\n```"
                answer = out_text.strip()
            else:
                cpt_records.append({"text": f"// Source: Strandset-Rust-v1 ({category})\n\n{code.strip()}"})
                continue

        # Add as both CPT and SFT
        cpt_records.append({"text": f"Question: {question}\n\nAnswer: {answer}"})
        sft_records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        })

    print(f"  CPT: {len(cpt_records):,}, SFT: {len(sft_records):,}")
    return cpt_records, sft_records


def add_vulnerability_dpo():
    """Generate DPO pairs from Solana vulnerability datasets."""
    print("\n=== Adding vulnerability data for DPO ===")
    from datasets import load_dataset

    dpo_chosen = []
    dpo_rejected = []

    # ArmurAI dataset: {code, vulnerabilities}
    print("  Loading ArmurAI/Solana_vulnerability_audit_dataset_V2...")
    try:
        ds = load_dataset("ArmurAI/Solana_vulnerability_audit_dataset_V2", split="train")
        print(f"    {len(ds)} examples")
        for row in ds:
            code = row.get("code", "")
            vulns = row.get("vulnerabilities", [])
            if not code or not vulns:
                continue

            prompt = f"Review this Solana program for security vulnerabilities:\n\n```rust\n{code.strip()[:2000]}\n```"

            vuln_list = vulns if isinstance(vulns, list) else [str(vulns)]
            chosen_answer = "I found the following security issues:\n\n" + "\n".join(f"- {v}" for v in vuln_list) + "\n\nThese should be fixed before deploying to mainnet."
            rejected_answer = "This code looks secure and follows Solana best practices. I don't see any vulnerabilities."

            chosen_msg = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": chosen_answer},
            ]
            rejected_msg = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": rejected_answer},
            ]
            dpo_chosen.append({"content": json.dumps(chosen_msg)})
            dpo_rejected.append({"content": json.dumps(rejected_msg)})
    except Exception as e:
        print(f"    ERROR: {e}")

    # FraChiacc99 dataset: {text} with [INST] format
    print("  Loading FraChiacc99/solana-vuln-rust...")
    try:
        ds = load_dataset("FraChiacc99/solana-vuln-rust", split="train")
        print(f"    {len(ds)} examples")
        for row in ds:
            text = row.get("text", "")
            if "[INST]" in text and "[/INST]" in text:
                # Parse instruction format
                parts = text.split("[/INST]")
                inst_part = parts[0].split("[INST]")[-1].strip()
                response_part = parts[1].strip() if len(parts) > 1 else ""

                if "vulnerability" in inst_part.lower() and response_part:
                    # The response identifies the vulnerability = chosen
                    chosen_msg = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": inst_part[:2000]},
                        {"role": "assistant", "content": response_part[:2000]},
                    ]
                    rejected_msg = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": inst_part[:2000]},
                        {"role": "assistant", "content": "This smart contract appears to be secure. I don't detect any vulnerabilities in the code."},
                    ]
                    dpo_chosen.append({"content": json.dumps(chosen_msg)})
                    dpo_rejected.append({"content": json.dumps(rejected_msg)})
    except Exception as e:
        print(f"    ERROR: {e}")

    print(f"  Total DPO pairs generated: {len(dpo_chosen)}")
    return dpo_chosen, dpo_rejected


def append_jsonl(records, path):
    with open(path, "a") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


def main():
    print(f"Data directory: {DATA_DIR}\n")

    # 1. Remove CC-BY-SA
    remove_ccbysa()

    # 2. Add Strandset Rust
    strand_cpt, strand_sft = add_strandset_rust()

    # 3. Add vulnerability DPO
    dpo_chosen, dpo_rejected = add_vulnerability_dpo()

    # 4. Write everything
    print("\n=== Writing new data ===")
    if strand_cpt:
        n = append_jsonl(strand_cpt, DATA_DIR / "cpt_train.jsonl")
        print(f"  Strandset CPT: +{n:,}")
    if strand_sft:
        n = append_jsonl(strand_sft, DATA_DIR / "sft_train.jsonl")
        print(f"  Strandset SFT: +{n:,}")
    if dpo_chosen:
        with open(DATA_DIR / "dpo-chosen-vuln.jsonl", "w") as f:
            for rec in dpo_chosen:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with open(DATA_DIR / "dpo-rejected-vuln.jsonl", "w") as f:
            for rec in dpo_rejected:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  DPO vulnerability pairs: +{len(dpo_chosen)}")

    # 5. Final counts
    print("\n=== Final counts ===")
    for fname in ["cpt_train.jsonl", "sft_train.jsonl"]:
        path = DATA_DIR / fname
        count = sum(1 for _ in open(path))
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"  {fname}: {count:,} records ({size_mb:.0f} MB)")

    dpo_total = 0
    for f in sorted(DATA_DIR.glob("dpo-chosen*.jsonl")):
        n = sum(1 for _ in open(f))
        dpo_total += n
        print(f"  {f.name}: {n} pairs")
    print(f"  DPO total: {dpo_total} chosen pairs")

    print("\nDone!")


if __name__ == "__main__":
    main()
