#!/usr/bin/env python3
"""Tag Rust code records with Anchor version class (modern/legacy/unknown).

Adds metadata.anchor_version_class to all Rust-language records in processed JSONL files.
Modern = Anchor 0.30+ patterns (declare_program!, solana-foundation/anchor, InitSpace).
Legacy = old patterns (declare_id!, coral-xyz/anchor).
Unknown = Rust code that doesn't clearly match either.

Used for upweighting modern patterns 2-3x during training data preparation.
"""
import json
import re
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

MODERN_MARKERS = [
    "declare_program!",
    "solana-foundation/anchor",
    "InitSpace",
    "ctx.bumps.",
    "#[account(init, payer",
    "anchor_lang::prelude::*",
]

LEGACY_MARKERS = [
    "declare_id!",
    "coral-xyz/anchor",
    "project-serum/anchor",
    "#[state]",  # deprecated Anchor pattern
]


def classify_anchor(content: str, language: str) -> str | None:
    """Classify Rust content as modern/legacy/unknown. Returns None for non-Rust."""
    if language != "rust":
        return None

    has_modern = any(m in content for m in MODERN_MARKERS)
    has_legacy = any(m in content for m in LEGACY_MARKERS)

    if has_modern and not has_legacy:
        return "modern"
    elif has_legacy and not has_modern:
        return "legacy"
    elif has_modern and has_legacy:
        return "mixed"  # contains both — likely migration example
    else:
        return "unknown"


def main():
    files = sorted(PROCESSED.glob("*.jsonl"))
    total_tagged = 0
    stats = {"modern": 0, "legacy": 0, "mixed": 0, "unknown": 0, "non_rust": 0}

    for path in files:
        lines = path.read_text().strip().split("\n")
        new_lines = []
        file_tagged = 0

        for line in lines:
            rec = json.loads(line)
            lang = rec.get("language", "")
            content = rec.get("content", "")

            cls = classify_anchor(content, lang)
            if cls is not None:
                if "metadata" not in rec:
                    rec["metadata"] = {}
                rec["metadata"]["anchor_version_class"] = cls
                stats[cls] += 1
                file_tagged += 1
            else:
                stats["non_rust"] += 1

            new_lines.append(json.dumps(rec, ensure_ascii=False))

        path.write_text("\n".join(new_lines) + "\n")
        if file_tagged > 0:
            total_tagged += file_tagged
            print(f"  {path.name}: {file_tagged} Rust records tagged")

    print(f"\nAnchor version tagging complete:")
    print(f"  Modern:   {stats['modern']:,}")
    print(f"  Legacy:   {stats['legacy']:,}")
    print(f"  Mixed:    {stats['mixed']:,}")
    print(f"  Unknown:  {stats['unknown']:,}")
    print(f"  Non-Rust: {stats['non_rust']:,}")
    print(f"  Total tagged: {total_tagged:,}")


if __name__ == "__main__":
    main()
