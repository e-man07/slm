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
    "#[account(init,",
    "#[account(init_if_needed",
    "#[account(mut,",
    "#[account(seeds",
    "anchor_lang::prelude::*",
    "#[program]",
    "#[derive(Accounts)]",
    "anchor_lang::system_program",
    "anchor_spl::",
    "require!(",
    "require_keys_eq!(",
    "require_gt!(",
    "msg!(",
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

    modern_count = sum(1 for m in MODERN_MARKERS if m in content)
    has_legacy = any(m in content for m in LEGACY_MARKERS)

    if modern_count >= 2 and not has_legacy:
        return "modern"
    elif has_legacy and modern_count == 0:
        return "legacy"
    elif has_legacy and modern_count >= 1:
        return "mixed"  # contains both — likely migration example
    elif modern_count == 1:
        return "unknown"  # only one marker — not confident
    else:
        return "unknown"


def main():
    """Tag Rust records with Anchor version class.

    By default runs in read-only analysis mode. Pass --write to update files.
    Note: filter.py already tags anchor_style during filtering, so this script
    is primarily useful for analysis/auditing before the filter stage.
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write changes back to files (destructive)")
    args = parser.parse_args()

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

        if args.write:
            path.write_text("\n".join(new_lines) + "\n")
        if file_tagged > 0:
            total_tagged += file_tagged
            print(f"  {path.name}: {file_tagged} Rust records tagged")

    print(f"\nAnchor version tagging {'complete' if args.write else '(analysis only, pass --write to save)'}:")
    print(f"  Modern:   {stats['modern']:,}")
    print(f"  Legacy:   {stats['legacy']:,}")
    print(f"  Mixed:    {stats['mixed']:,}")
    print(f"  Unknown:  {stats['unknown']:,}")
    print(f"  Non-Rust: {stats['non_rust']:,}")
    print(f"  Total tagged: {total_tagged:,}")


if __name__ == "__main__":
    main()
