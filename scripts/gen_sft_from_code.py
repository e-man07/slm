#!/usr/bin/env python3
"""Template-based SFT variant generator for Solana code training data.

Takes raw SFT records (code write examples) and generates 3-5 variants per
record: write, explain, complete, fix, and refactor. All variant generation
is heuristic/template-based — no LLM API calls.

Usage:
    python scripts/gen_sft_from_code.py                     # run full pipeline
    python scripts/gen_sft_from_code.py --dry-run            # preview stats without writing
    python scripts/gen_sft_from_code.py --fix-ratio 0.5      # increase fix variant ratio
"""

from __future__ import annotations

import json
import random
import re
import textwrap
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from schema import detect_framework, infer_domain

app = typer.Typer(invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "collected"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_FILES = [
    INPUT_DIR / "solana_code_sft.jsonl",
    INPUT_DIR / "pinocchio_sft.jsonl",
]

OUTPUT_FILES = {
    "write": OUTPUT_DIR / "sft-code-write.jsonl",
    "explain": OUTPUT_DIR / "sft-code-explain.jsonl",
    "complete": OUTPUT_DIR / "sft-code-complete.jsonl",
    "fix": OUTPUT_DIR / "sft-code-fix.jsonl",
    "refactor": OUTPUT_DIR / "sft-code-refactor.jsonl",
}

# Minimum line count for the "complete" variant
MIN_LINES_FOR_COMPLETE = 10

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_sft_records(path: Path) -> list[dict]:
    """Load SFT records from a JSONL file."""
    records: list[dict] = []
    if not path.exists():
        console.print(f"  [yellow]Input not found: {path.name} — skipping[/yellow]")
        return records
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if "messages" in record and len(record["messages"]) >= 3:
                    records.append(record)
            except json.JSONDecodeError:
                console.print(
                    f"  [yellow]Skipping malformed JSON at {path.name}:{line_num}[/yellow]"
                )
    return records


def extract_code_from_record(record: dict) -> str:
    """Extract the assistant's code response from an SFT record."""
    for msg in record["messages"]:
        if msg["role"] == "assistant":
            return msg["content"]
    return ""


def extract_system_prompt(record: dict) -> str:
    """Extract the system prompt from an SFT record."""
    for msg in record["messages"]:
        if msg["role"] == "system":
            return msg["content"]
    return ""


def extract_user_prompt(record: dict) -> str:
    """Extract the user prompt from an SFT record."""
    for msg in record["messages"]:
        if msg["role"] == "user":
            return msg["content"]
    return ""


# ---------------------------------------------------------------------------
# Heuristic code analysis
# ---------------------------------------------------------------------------

# Patterns for detecting Solana/Anchor concepts in code
_PDA_PATTERN = re.compile(r"(find_program_address|seeds\s*=|Pubkey::find_program_address)")
_CPI_PATTERN = re.compile(r"(invoke|invoke_signed|CpiContext|cpi::)")
_TOKEN_PATTERN = re.compile(
    r"(mint_to|transfer|burn|freeze|thaw|spl_token|token::|MintTo|Transfer|Burn)"
)
_ACCOUNT_VALIDATION_PATTERN = re.compile(
    r"(#\[account\(|constraint\s*=|has_one\s*=|Signer|AccountInfo)"
)
_MATH_PATTERN = re.compile(r"(checked_add|checked_sub|checked_mul|checked_div|saturating_)")
_INIT_PATTERN = re.compile(r"(#\[account\(\s*init|init_if_needed)")
_CLOSE_PATTERN = re.compile(r"(close\s*=|#\[account\(\s*.*close)")
_ERROR_PATTERN = re.compile(r"(#\[error_code\]|err!\(|require!\(|require_keys_eq!)")
_EVENT_PATTERN = re.compile(r"(emit!\(|#\[event\])")
_STATE_PATTERN = re.compile(r"(#\[account\]|#\[derive\(.*Accounts)")
_SERIALIZATION_PATTERN = re.compile(r"(BorshSerialize|BorshDeserialize|AnchorSerialize)")

# Function/struct name extraction
_FN_NAME_RE = re.compile(r"(?:pub\s+)?fn\s+(\w+)")
_STRUCT_NAME_RE = re.compile(r"(?:pub\s+)?struct\s+(\w+)")
_ENUM_NAME_RE = re.compile(r"(?:pub\s+)?enum\s+(\w+)")
_IMPL_NAME_RE = re.compile(r"impl(?:<[^>]*>)?\s+(\w+)")

# Legacy pattern detection
_LEGACY_DECLARE_ID = re.compile(r"declare_id!")
_LEGACY_CORAL = re.compile(r"coral-xyz/anchor")
_LEGACY_SERUM = re.compile(r"project-serum/anchor")
_LEGACY_STATE_ATTR = re.compile(r"#\[state\]")


def _extract_names(code: str) -> list[str]:
    """Extract function, struct, and enum names from code."""
    names: list[str] = []
    for pattern in [_FN_NAME_RE, _STRUCT_NAME_RE, _ENUM_NAME_RE, _IMPL_NAME_RE]:
        names.extend(pattern.findall(code))
    return names


def _extract_doc_comments(code: str) -> list[str]:
    """Extract doc comment lines from code."""
    comments: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("///") or stripped.startswith("//!"):
            text = stripped.lstrip("/!").strip()
            if text:
                comments.append(text)
    return comments


def _detect_concepts(code: str) -> list[str]:
    """Detect Solana concepts present in the code."""
    concepts: list[str] = []
    checks = [
        (_PDA_PATTERN, "Program Derived Address (PDA) derivation"),
        (_CPI_PATTERN, "Cross-Program Invocation (CPI)"),
        (_TOKEN_PATTERN, "SPL token operations"),
        (_ACCOUNT_VALIDATION_PATTERN, "account validation and constraints"),
        (_MATH_PATTERN, "safe arithmetic (checked math)"),
        (_INIT_PATTERN, "account initialization"),
        (_CLOSE_PATTERN, "account closing"),
        (_ERROR_PATTERN, "custom error handling"),
        (_EVENT_PATTERN, "event emission"),
        (_STATE_PATTERN, "program state/account definitions"),
        (_SERIALIZATION_PATTERN, "Borsh serialization"),
    ]
    for pattern, description in checks:
        if pattern.search(code):
            concepts.append(description)
    return concepts


def detect_legacy_patterns(code: str) -> bool:
    """Return True if code contains legacy Anchor patterns worth modernizing."""
    return bool(
        _LEGACY_DECLARE_ID.search(code)
        or _LEGACY_CORAL.search(code)
        or _LEGACY_SERUM.search(code)
        or _LEGACY_STATE_ATTR.search(code)
    )


# ---------------------------------------------------------------------------
# Explain variant — heuristic response generation
# ---------------------------------------------------------------------------

_EXPLAIN_TEMPLATES = [
    "Explain what this Solana program code does.",
    "Explain what this code does in a Solana program.",
    "Walk through this Solana code and explain its purpose.",
    "What does the following Solana program code do?",
    "Describe the functionality of this Solana code.",
]


def generate_explain_response(code: str) -> str:
    """Generate a heuristic explanation of the code based on pattern detection."""
    framework = detect_framework(code)
    domain = infer_domain(code)
    concepts = _detect_concepts(code)
    names = _extract_names(code)
    doc_comments = _extract_doc_comments(code)

    # Build framework description
    framework_desc = {
        "anchor": "an Anchor framework",
        "pinocchio": "a Pinocchio (zero-copy)",
        "native": "a native Solana",
    }[framework]

    # Build domain description
    domain_desc = {
        "defi": "DeFi (decentralized finance)",
        "nft": "NFT/metadata",
        "token": "token management",
        "governance": "governance",
        "staking": "staking",
        "general": "general-purpose",
    }[domain]

    # Start building explanation
    parts: list[str] = []

    # Opening summary
    if doc_comments:
        doc_summary = " ".join(doc_comments[:3])
        parts.append(
            f"This is {framework_desc} Solana program code for {domain_desc} "
            f"functionality. Based on the documentation: {doc_summary}"
        )
    else:
        fn_names = [n for n in names if n not in ("Self", "self", "new", "default")]
        if fn_names:
            natural_names = ", ".join(
                f"`{n}`" for n in fn_names[:4]
            )
            parts.append(
                f"This is {framework_desc} Solana program code for {domain_desc} "
                f"functionality. It defines {natural_names}."
            )
        else:
            parts.append(
                f"This is {framework_desc} Solana program code for {domain_desc} "
                f"functionality."
            )

    # Describe detected concepts
    if concepts:
        parts.append("\nKey concepts used in this code:")
        for concept in concepts:
            parts.append(f"- **{concept}**")

    # Describe struct fields if present
    field_matches = re.findall(r"pub\s+(\w+)\s*:\s*([^,\n}]+)", code)
    if field_matches:
        field_desc = ", ".join(f"`{name}: {typ.strip()}`" for name, typ in field_matches[:6])
        parts.append(f"\nThe code defines fields including: {field_desc}.")

    # Framework-specific notes
    if framework == "anchor":
        if _INIT_PATTERN.search(code):
            parts.append(
                "\nThe account initialization uses Anchor's `init` constraint, which "
                "handles space allocation and rent exemption automatically."
            )
        if _PDA_PATTERN.search(code):
            parts.append(
                "\nPDAs (Program Derived Addresses) are used to create deterministic "
                "account addresses derived from seeds, ensuring only the program can "
                "sign for these accounts."
            )
    elif framework == "pinocchio":
        parts.append(
            "\nThis uses the Pinocchio framework for zero-copy account parsing, "
            "which provides better performance than Anchor by avoiding "
            "deserialization overhead."
        )

    # Security notes
    if _ACCOUNT_VALIDATION_PATTERN.search(code):
        parts.append(
            "\nThe code includes account validation constraints to ensure "
            "only authorized accounts can interact with the instruction."
        )
    if _MATH_PATTERN.search(code):
        parts.append(
            "\nSafe arithmetic (checked/saturating operations) is used to prevent "
            "integer overflow vulnerabilities."
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Complete variant — partial code generation
# ---------------------------------------------------------------------------

_COMPLETE_TEMPLATES = [
    "Complete this Solana program code.",
    "Finish implementing this Solana program.",
    "Complete the following partial Solana code.",
    "Fill in the rest of this Solana program implementation.",
]


def create_partial_code(code: str) -> str:
    """Return approximately the first 40% of the code as a partial snippet."""
    lines = code.splitlines()
    cut_point = max(3, int(len(lines) * 0.4))

    # Try to cut at a line that ends with { or after a blank line for cleaner context
    best_cut = cut_point
    for i in range(cut_point, min(cut_point + 5, len(lines))):
        stripped = lines[i].strip()
        if stripped.endswith("{") or stripped == "" or stripped.endswith(","):
            best_cut = i + 1
            break

    partial = "\n".join(lines[:best_cut])
    partial += "\n    // ... complete the implementation"
    return partial


# ---------------------------------------------------------------------------
# Fix variant — deliberate bug injection
# ---------------------------------------------------------------------------

_FIX_TEMPLATES = [
    "This Solana code has a bug. Find and fix it.",
    "There is a bug in the following Solana program. Identify and correct it.",
    "Debug this Solana code — it contains an error that needs to be fixed.",
    "Fix the bug in this Solana program code.",
]


def _inject_missing_mut(code: str) -> tuple[str, str] | None:
    """Remove `mut` from a signer/payer account constraint."""
    # Match: #[account(mut, ...)] or #[account(mut)] on a line with signer/payer nearby
    pattern = re.compile(r"(#\[account\()mut(\s*,\s*)")
    match = pattern.search(code)
    if match:
        broken = pattern.sub(r"\1", code, count=1)
        # Clean up: #[account(, -> #[account(
        broken = broken.replace("#[account(,", "#[account(")
        broken = broken.replace("#[account( ,", "#[account(")
        desc = (
            "The `mut` constraint was missing from an account that needs to be mutable. "
            "Without `mut`, the runtime will reject any attempt to modify this account's "
            "data or debit its lamports."
        )
        return broken, desc
    return None


def _inject_missing_bump(code: str) -> tuple[str, str] | None:
    """Remove `bump` from a seeds constraint."""
    pattern = re.compile(r",\s*bump\s*(?:=\s*\w+(?:\.\w+)*)?\s*(?=[,\]\)])")
    match = pattern.search(code)
    if match:
        broken = pattern.sub("", code, count=1)
        desc = (
            "The `bump` was missing from the PDA seeds constraint. Without specifying "
            "the bump, the program cannot properly validate the PDA derivation, which "
            "could allow an attacker to pass an arbitrary account."
        )
        return broken, desc
    return None


def _inject_missing_signer(code: str) -> tuple[str, str] | None:
    """Remove a Signer type annotation, replacing with AccountInfo."""
    pattern = re.compile(r"(pub\s+\w+\s*:\s*)Signer<'info>")
    match = pattern.search(code)
    if match:
        broken = pattern.sub(r"\1AccountInfo<'info>", code, count=1)
        desc = (
            "A `Signer` type was replaced with `AccountInfo`, removing the signer "
            "verification. This means the instruction no longer checks that the "
            "account actually signed the transaction, which is a critical security "
            "vulnerability."
        )
        return broken, desc
    return None


def _inject_unchecked_math(code: str) -> tuple[str, str] | None:
    """Replace a checked_add/checked_sub with unchecked arithmetic."""
    patterns = [
        (re.compile(r"(\w+)\.checked_add\((\w+)\)\.unwrap\(\)"), r"\1 + \2"),
        (re.compile(r"(\w+)\.checked_sub\((\w+)\)\.unwrap\(\)"), r"\1 - \2"),
        (re.compile(r"(\w+)\.checked_mul\((\w+)\)\.unwrap\(\)"), r"\1 * \2"),
        (re.compile(r"(\w+)\.checked_add\((\w+)\)\?"), r"\1 + \2"),
        (re.compile(r"(\w+)\.checked_sub\((\w+)\)\?"), r"\1 - \2"),
        (re.compile(r"(\w+)\.checked_mul\((\w+)\)\?"), r"\1 * \2"),
    ]
    for pattern, replacement in patterns:
        match = pattern.search(code)
        if match:
            broken = pattern.sub(replacement, code, count=1)
            desc = (
                "Unchecked arithmetic was used instead of `checked_add`/`checked_sub`/"
                "`checked_mul`. This can cause integer overflow or underflow, leading "
                "to incorrect calculations or exploitable vulnerabilities. Always use "
                "checked or saturating arithmetic in Solana programs."
            )
            return broken, desc
    return None


# Ordered by likelihood of finding a match
_BUG_INJECTORS = [
    _inject_missing_mut,
    _inject_missing_bump,
    _inject_unchecked_math,
    _inject_missing_signer,
]


def create_broken_code(code: str) -> tuple[str, str] | None:
    """Inject a deliberate bug into the code.

    Returns (broken_code, bug_description) or None if no bug could be injected.
    """
    # Shuffle injectors so we get variety across records
    injectors = _BUG_INJECTORS.copy()
    random.shuffle(injectors)
    for injector in injectors:
        result = injector(code)
        if result is not None:
            broken_code, description = result
            # Sanity check: broken code must actually differ from original
            if broken_code != code:
                return broken_code, description
    return None


# ---------------------------------------------------------------------------
# Refactor variant — modernization
# ---------------------------------------------------------------------------

_REFACTOR_TEMPLATES = [
    "Modernize this Solana code to use Anchor 0.30+ patterns.",
    "Refactor this legacy Solana code to use modern Anchor patterns.",
    "Update this code to follow current Anchor best practices (0.30+).",
]


def _generate_refactor_notes(code: str) -> list[str]:
    """Generate notes about what was modernized."""
    notes: list[str] = []
    if _LEGACY_DECLARE_ID.search(code):
        notes.append(
            "Replaced `declare_id!` with `declare_program!` (Anchor 0.30+ pattern)"
        )
    if _LEGACY_CORAL.search(code):
        notes.append(
            "Updated import references from `coral-xyz/anchor` to "
            "`solana-foundation/anchor`"
        )
    if _LEGACY_SERUM.search(code):
        notes.append(
            "Updated import references from `project-serum/anchor` to "
            "`solana-foundation/anchor`"
        )
    if _LEGACY_STATE_ATTR.search(code):
        notes.append(
            "Replaced deprecated `#[state]` attribute with modern account patterns"
        )
    return notes


# ---------------------------------------------------------------------------
# Variant generation — main logic
# ---------------------------------------------------------------------------


def _make_sft_record(
    system: str, user: str, assistant: str, variant: str
) -> dict:
    """Create a ChatML SFT training record with variant metadata."""
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ],
        "_metadata": {
            "sft_variant": variant,
            "framework": "",  # filled in by caller
            "domain": "",  # filled in by caller
        },
    }


def generate_variants(
    record: dict,
    *,
    fix_ratio: float = 0.3,
    rng: random.Random,
) -> dict[str, list[dict]]:
    """Generate all applicable variants for a single SFT record.

    Returns a dict mapping variant type to list of generated records.
    """
    code = extract_code_from_record(record)
    system_prompt = extract_system_prompt(record)
    user_prompt = extract_user_prompt(record)

    if not code.strip():
        return {}

    framework = detect_framework(code)
    domain = infer_domain(code)
    code_lines = code.splitlines()
    variants: dict[str, list[dict]] = {}

    def _tag(rec: dict) -> dict:
        """Fill in framework and domain metadata."""
        rec["_metadata"]["framework"] = framework
        rec["_metadata"]["domain"] = domain
        return rec

    # --- 1. Write variant: pass through original ---
    write_rec = _make_sft_record(system_prompt, user_prompt, code, "write")
    variants["write"] = [_tag(write_rec)]

    # --- 2. Explain variant ---
    explain_prompt = rng.choice(_EXPLAIN_TEMPLATES)
    explain_user = f"{explain_prompt}\n\n```rust\n{code}\n```"
    explain_response = generate_explain_response(code)
    explain_rec = _make_sft_record(
        system_prompt, explain_user, explain_response, "explain"
    )
    variants["explain"] = [_tag(explain_rec)]

    # --- 3. Complete variant (only for code > MIN_LINES_FOR_COMPLETE lines) ---
    if len(code_lines) > MIN_LINES_FOR_COMPLETE:
        complete_prompt = rng.choice(_COMPLETE_TEMPLATES)
        partial = create_partial_code(code)
        complete_user = f"{complete_prompt}\n\n```rust\n{partial}\n```"
        complete_rec = _make_sft_record(
            system_prompt, complete_user, code, "complete"
        )
        variants["complete"] = [_tag(complete_rec)]

    # --- 4. Fix variant (randomly selected subset) ---
    if rng.random() < fix_ratio:
        result = create_broken_code(code)
        if result is not None:
            broken_code, bug_description = result
            fix_prompt = rng.choice(_FIX_TEMPLATES)
            fix_user = f"{fix_prompt}\n\n```rust\n{broken_code}\n```"
            fix_response = (
                f"Here is the corrected code:\n\n```rust\n{code}\n```\n\n"
                f"**Bug fix:** {bug_description}"
            )
            fix_rec = _make_sft_record(
                system_prompt, fix_user, fix_response, "fix"
            )
            variants["fix"] = [_tag(fix_rec)]

    # --- 5. Refactor variant (only for legacy patterns) ---
    if detect_legacy_patterns(code):
        refactor_prompt = rng.choice(_REFACTOR_TEMPLATES)
        refactor_user = f"{refactor_prompt}\n\n```rust\n{code}\n```"

        # Apply simple modernization transforms for the response
        modernized = code
        modernized = _LEGACY_DECLARE_ID.sub("declare_program!", modernized)
        modernized = _LEGACY_CORAL.sub("solana-foundation/anchor", modernized)
        modernized = _LEGACY_SERUM.sub("solana-foundation/anchor", modernized)

        refactor_notes = _generate_refactor_notes(code)
        notes_text = "\n".join(f"- {n}" for n in refactor_notes)
        refactor_response = (
            f"Here is the modernized version:\n\n```rust\n{modernized}\n```\n\n"
            f"**Changes made:**\n{notes_text}"
        )
        refactor_rec = _make_sft_record(
            system_prompt, refactor_user, refactor_response, "refactor"
        )
        variants["refactor"] = [_tag(refactor_rec)]

    return variants


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------


def write_variant_file(path: Path, records: list[dict]) -> int:
    """Write variant records to a JSONL file. Returns count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview stats without writing output files"
    ),
    fix_ratio: float = typer.Option(
        0.3, "--fix-ratio", help="Fraction of records to generate fix variants for"
    ),
    seed: int = typer.Option(
        42, "--seed", help="Random seed for reproducibility"
    ),
):
    """Generate SFT variant training data from collected Solana code records."""
    rng = random.Random(seed)

    # --- Phase 1: Load input records ---
    console.print("\n[bold blue]Phase 1: Loading input records[/bold blue]")
    all_records: list[dict] = []
    for input_path in INPUT_FILES:
        records = load_sft_records(input_path)
        if records:
            console.print(f"  Loaded {len(records):,} records from {input_path.name}")
            all_records.extend(records)

    if not all_records:
        console.print("[red]No input records found. Run collect_solana_code.py first.[/red]")
        raise typer.Exit(code=1)

    console.print(f"  [bold]Total input records: {len(all_records):,}[/bold]")

    # --- Phase 2: Generate variants ---
    console.print("\n[bold blue]Phase 2: Generating variants[/bold blue]")
    variant_buckets: dict[str, list[dict]] = {
        "write": [],
        "explain": [],
        "complete": [],
        "fix": [],
        "refactor": [],
    }

    for record in track(all_records, description="Generating variants..."):
        variants = generate_variants(record, fix_ratio=fix_ratio, rng=rng)
        for variant_type, variant_records in variants.items():
            variant_buckets[variant_type].extend(variant_records)

    # --- Phase 3: Stats and output ---
    console.print("\n[bold blue]Phase 3: Writing output[/bold blue]")

    table = Table(title="SFT Variant Generation Results")
    table.add_column("Variant", style="cyan")
    table.add_column("Records", justify="right", style="green")
    table.add_column("Output File", style="dim")

    total_variants = 0
    for variant_type, records in variant_buckets.items():
        count = len(records)
        total_variants += count
        output_path = OUTPUT_FILES[variant_type]

        if not dry_run and count > 0:
            write_variant_file(output_path, records)

        status = str(output_path.relative_to(PROJECT_ROOT))
        if dry_run:
            status += " (dry run)"
        elif count == 0:
            status += " (skipped — no records)"

        table.add_row(variant_type, f"{count:,}", status)

    table.add_section()
    table.add_row("[bold]Total[/bold]", f"[bold]{total_variants:,}[/bold]", "")
    multiplier = total_variants / len(all_records) if all_records else 0
    table.add_row("Multiplier", f"{multiplier:.1f}x", "")

    console.print(table)

    if dry_run:
        console.print("\n[yellow]Dry run — no files written.[/yellow]")
    else:
        console.print(f"\n[bold green]Done![/bold green] Wrote {total_variants:,} variant records.")


if __name__ == "__main__":
    app()
