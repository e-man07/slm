#!/usr/bin/env python3
"""Validate system prompt consistency across all inference surfaces.

Checks:
1. No code template contains declare_id!("...") — the critical contradiction
2. All inference prompts include the training-tier prefix text
3. The canonical prompts/sealevel.json is well-formed
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Key phrases that must appear in all inference prompts
REQUIRED_PHRASES = [
    "Sealevel",
    "Solana and Anchor",
    "Anchor 0.30+",
]

# Files that contain inference system prompts (not training scripts)
INFERENCE_PROMPT_FILES = [
    "slm-web/lib/constants.ts",
    "slm-mcp/src/lib/constants.ts",
    "slm-cli/sealevel_cli/client.py",
    "slm-cli/slm_cli/client.py",
    "slm-vscode/src/chat-participant.ts",
    "deploy/rag-api/app.py",
]

# Pattern that should NOT appear in code templates
DECLARE_ID_IN_TEMPLATE = re.compile(r'declare_id!\s*\(\s*"[A-Za-z0-9]+"')


def check_no_declare_id_in_templates() -> list[str]:
    """Ensure no code template contains declare_id!("...")."""
    errors = []
    for rel_path in INFERENCE_PROMPT_FILES:
        fpath = ROOT / rel_path
        if not fpath.exists():
            continue
        content = fpath.read_text()
        if DECLARE_ID_IN_TEMPLATE.search(content):
            errors.append(
                f"  FAIL: {rel_path} contains declare_id!(\"...\") in code template"
            )
    return errors


def check_training_prefix() -> list[str]:
    """Ensure all inference prompts contain key training-tier phrases."""
    errors = []
    for rel_path in INFERENCE_PROMPT_FILES:
        fpath = ROOT / rel_path
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for phrase in REQUIRED_PHRASES:
            if phrase not in content:
                errors.append(
                    f"  FAIL: {rel_path} missing required phrase: '{phrase}'"
                )
    return errors


def check_canonical_json() -> list[str]:
    """Validate prompts/sealevel.json structure."""
    errors = []
    json_path = ROOT / "prompts" / "sealevel.json"
    if not json_path.exists():
        return ["  FAIL: prompts/sealevel.json does not exist"]

    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError as e:
        return [f"  FAIL: prompts/sealevel.json is invalid JSON: {e}"]

    for tier in ("training", "standard", "full"):
        if tier not in data.get("tiers", {}):
            errors.append(f"  FAIL: missing tier '{tier}' in sealevel.json")

    # Training tier must not contain declare_id!("...")
    training = data.get("tiers", {}).get("training", "")
    if DECLARE_ID_IN_TEMPLATE.search(training):
        errors.append(
            "  FAIL: training tier in sealevel.json contains declare_id!(\"...\")"
        )

    # Full tier must contain the identity
    full = data.get("tiers", {}).get("full", "")
    if "Solana Language Model" not in full:
        errors.append(
            "  FAIL: full tier missing 'Solana Language Model' identity"
        )

    return errors


def check_identity() -> list[str]:
    """Ensure all inference prompts identify as 'Sealevel'."""
    errors = []
    for rel_path in INFERENCE_PROMPT_FILES:
        fpath = ROOT / rel_path
        if not fpath.exists():
            continue
        content = fpath.read_text()
        if "Sealevel" not in content:
            errors.append(f"  FAIL: {rel_path} missing 'Sealevel' identity")
    return errors


def main() -> int:
    print("System Prompt Consistency Check")
    print("=" * 50)

    all_errors: list[str] = []

    print("\n1. No declare_id! in code templates...")
    errs = check_no_declare_id_in_templates()
    all_errors.extend(errs)
    print("  PASS" if not errs else "\n".join(errs))

    print("\n2. Training prefix present in all prompts...")
    errs = check_training_prefix()
    all_errors.extend(errs)
    print("  PASS" if not errs else "\n".join(errs))

    print("\n3. Canonical sealevel.json valid...")
    errs = check_canonical_json()
    all_errors.extend(errs)
    print("  PASS" if not errs else "\n".join(errs))

    print("\n4. Sealevel identity in all prompts...")
    errs = check_identity()
    all_errors.extend(errs)
    print("  PASS" if not errs else "\n".join(errs))

    print("\n" + "=" * 50)
    if all_errors:
        print(f"FAILED: {len(all_errors)} error(s)")
        return 1
    else:
        print("ALL CHECKS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
