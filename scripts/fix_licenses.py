#!/usr/bin/env python3
"""Fix license fields in processed JSONL files based on verified HF card audit."""
import json
from pathlib import Path

PROCESSED = Path(__file__).parent.parent / "data" / "processed"

LICENSE_MAP = {
    "hf-lumo-fart.jsonl": "AGPL-3.0",
    "hf-lumo-novel.jsonl": "AGPL-3.0",
    "hf-lumo-iris.jsonl": "AGPL-3.0",
    "hf-lumo-8b.jsonl": "AGPL-3.0",
    "hf-learn-rust.jsonl": "Apache-2.0",
    "hf-stack-rust-clean.jsonl": "OpenRAIL",
}

for filename, new_license in LICENSE_MAP.items():
    path = PROCESSED / filename
    if not path.exists():
        print(f"  SKIP {filename} (not found)")
        continue

    lines = path.read_text().strip().split("\n")
    updated = 0
    new_lines = []
    for line in lines:
        rec = json.loads(line)
        if rec.get("license") != new_license:
            rec["license"] = new_license
            updated += 1
        new_lines.append(json.dumps(rec, ensure_ascii=False))

    path.write_text("\n".join(new_lines) + "\n")
    print(f"  {filename}: {updated}/{len(lines)} records updated → {new_license}")

print("\nDone. License fields updated.")
