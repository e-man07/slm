"""Mix tool-calling records with Solana replay for continual training.

Reads:
  - All `data/processed/sft_tool_calling_*.jsonl` files (the new tool data)
  - The HF Solana dataset `WhyParabola/sealevel-solana-dataset` (270K Solana records)

Writes:
  - `data/final/sft_train_with_tools.jsonl` — interleaved 5:1 Solana:tools

The mixed file is what `train_sft.py` consumes for continual training.

Usage:
    python scripts/mix_tool_calling_with_solana.py \
        --solana-replay 50000 \
        --tool-records 10000 \
        --output data/final/sft_train_with_tools.jsonl

The Solana replay can be a local JSONL file too (--solana-source path/to/file.jsonl).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from schema import Record  # noqa: E402

DEFAULT_TOOL_DIR = ROOT / "data" / "processed"
DEFAULT_OUTPUT = ROOT / "data" / "final" / "sft_train_with_tools.jsonl"

DEFAULT_SOLANA_HF_DATASET = "WhyParabola/sealevel-solana-dataset"


def load_tool_records(tool_dir: Path, target: int | None) -> list[dict]:
    """Load all sft_tool_calling_*.jsonl files."""
    records: list[dict] = []
    for path in sorted(tool_dir.glob("sft_tool_calling_*.jsonl")):
        print(f"  Loading {path.name}...")
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    print(f"  Total tool records: {len(records)}")
    if target is not None and len(records) > target:
        rng = random.Random(42)
        records = rng.sample(records, target)
        print(f"  Sampled to {target}")
    return records


def load_solana_replay_local(path: Path, target: int) -> list[dict]:
    """Load Solana replay from a local JSONL file."""
    records: list[dict] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    print(f"  Loaded {len(records)} Solana records from {path}")
    if len(records) > target:
        rng = random.Random(42)
        records = rng.sample(records, target)
        print(f"  Sampled to {target}")
    return records


def load_solana_replay_hf(dataset_name: str, target: int) -> list[dict]:
    """Load Solana replay from HuggingFace, sampling to target.

    The HF dataset has shape {"messages": [...], "split": "train"}.
    We need to convert these into the same Record format we use for tool data.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("ERROR: `datasets` not installed. Either:")
        print("  pip install datasets")
        print("  OR use --solana-source path/to/local.jsonl")
        sys.exit(1)

    print(f"  Loading {dataset_name} from HuggingFace (streaming mode)...")
    # Streaming mode tolerates mixed schemas across files
    ds = load_dataset(dataset_name, split="train", streaming=True)

    records: list[dict] = []
    rng = random.Random(42)
    # Reservoir sampling so we don't iterate the whole dataset
    seen = 0
    for item in ds:
        # Some records have `messages`, others might have `text`
        if "messages" in item and item["messages"]:
            messages = item["messages"]
            content = json.dumps({"messages": messages}, ensure_ascii=False, separators=(",", ":"))
        elif "text" in item and item["text"]:
            # Wrap raw text as a single user/assistant turn (synthetic shape)
            # Skip — these don't fit our format cleanly
            seen += 1
            continue
        else:
            seen += 1
            continue

        record = {
            "id": Record.make_id(content),
            "source": "hf/sealevel-solana-dataset",
            "source_type": "qa",
            "content": content,
            "language": "en",
            "license": "synthetic-mit",
            "metadata": {"method": "solana_replay", "hf_seen": seen},
        }

        if len(records) < target:
            records.append(record)
        else:
            # Reservoir sampling: replace random existing record
            j = rng.randint(0, seen)
            if j < target:
                records[j] = record

        seen += 1
        if seen % 10000 == 0:
            print(f"  Streamed {seen} records, kept {len(records)}")

        # Early exit once we've sampled enough
        if seen >= target * 6 and len(records) >= target:
            break

    print(f"  Loaded {len(records)} Solana records (replay) from {seen} streamed")
    return records


def write_mixed(records: list[dict], output: Path) -> None:
    """Write final mixed JSONL."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(records)} records to {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-dir", type=Path, default=DEFAULT_TOOL_DIR,
                        help="Directory containing sft_tool_calling_*.jsonl files")
    parser.add_argument("--solana-source", type=Path, default=None,
                        help="Local JSONL path for Solana replay (overrides HF)")
    parser.add_argument("--solana-hf", type=str, default=DEFAULT_SOLANA_HF_DATASET,
                        help="HuggingFace dataset name for Solana replay")
    parser.add_argument("--solana-replay", type=int, default=50_000,
                        help="Number of Solana records to mix in")
    parser.add_argument("--tool-records", type=int, default=10_000,
                        help="Number of tool records to use (sampled if more available)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("=" * 60)
    print("Loading tool-calling records...")
    print("=" * 60)
    tool_records = load_tool_records(args.tool_dir, args.tool_records)

    print("\n" + "=" * 60)
    print("Loading Solana replay records...")
    print("=" * 60)
    if args.solana_source and args.solana_source.exists():
        solana_records = load_solana_replay_local(args.solana_source, args.solana_replay)
    else:
        if args.solana_source:
            print(f"WARNING: --solana-source {args.solana_source} not found, falling back to HF")
        solana_records = load_solana_replay_hf(args.solana_hf, args.solana_replay)

    print("\n" + "=" * 60)
    print("Mixing & shuffling...")
    print("=" * 60)
    print(f"  Solana: {len(solana_records)} records")
    print(f"  Tools:  {len(tool_records)} records")
    print(f"  Ratio:  {len(solana_records) / max(1, len(tool_records)):.1f}:1 (Solana:Tools)")

    mixed = solana_records + tool_records
    rng = random.Random(args.seed)
    rng.shuffle(mixed)

    write_mixed(mixed, args.output)
    print(f"\nFinal: {len(mixed)} records ({len(solana_records)} Solana + {len(tool_records)} Tools)")


if __name__ == "__main__":
    main()
