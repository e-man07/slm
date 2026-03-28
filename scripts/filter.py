#!/usr/bin/env python3
"""Stage 3: Quality filtering and Anchor version tagging.

Filters:
- rustfmt syntax check on Rust code
- cargo check type checking (optional, slow)
- KenLM perplexity filtering on docs (optional, removes >95th percentile)
- Length filter (50-32K tokens, estimated as chars/4)
- Anchor version tagging and modern pattern detection
- Content quality heuristics

Usage:
    python scripts/filter.py
    python scripts/filter.py --skip-rustfmt       # skip Rust syntax checking
    python scripts/filter.py --enable-kenlm        # enable perplexity filtering
    python scripts/filter.py --no-skip-cargo        # enable cargo check (slow)
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track

from schema import Record, is_modern_anchor, read_jsonl, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
DEDUPED_DIR = PROJECT_ROOT / "data" / "deduped"
FINAL_DIR = PROJECT_ROOT / "data" / "final"

# Token estimation: ~4 chars per token for code
CHARS_PER_TOKEN = 4
DEFAULT_MIN_TOKENS = 50
DEFAULT_MAX_TOKENS = 32_000


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def check_rustfmt(code: str) -> bool:
    """Run rustfmt on code via stdin. Returns True if valid syntax."""
    try:
        result = subprocess.run(
            ["rustfmt", "--check", "--edition", "2021"],
            input=code,
            capture_output=True,
            text=True,
            timeout=10,
        )
        # rustfmt returns 0 if formatted, 1 if needs formatting (but valid)
        # We only care about syntax validity, not formatting
        # A parse error returns exit code 1 with specific error messages
        if result.returncode == 0:
            return True
        # Check if it's a formatting issue (valid syntax) vs parse error
        if "error[" in result.stderr or "error:" in result.stderr:
            return False
        return True  # Formatting difference is fine
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True  # If rustfmt unavailable, don't filter


def check_cargo(code: str, cargo_project: Path) -> bool:
    """Run cargo check on code. Returns True if type-checks.

    Uses a cached Cargo project to avoid re-downloading deps.
    """
    main_rs = cargo_project / "src" / "main.rs"
    main_rs.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            ["cargo", "check", "--quiet"],
            cwd=str(cargo_project),
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **dict(__import__("os").environ),
                "CARGO_TARGET_DIR": str(cargo_project / "target"),
            },
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return True  # Don't filter on timeout


def is_likely_complete_rust(content: str) -> bool:
    """Heuristic: check if Rust content is a complete compilable unit vs a snippet."""
    # Snippets without fn/struct/mod/use are likely fragments
    has_structure = bool(re.search(r"\b(fn |struct |mod |impl |trait |enum |use )", content))
    return has_structure


def quality_heuristics(record: Record) -> tuple[bool, str]:
    """Apply content quality heuristics. Returns (pass, reason)."""
    content = record.content

    # Length check (using char estimation)
    est_tokens = estimate_tokens(content)
    if est_tokens < DEFAULT_MIN_TOKENS:
        return False, f"too_short ({est_tokens} est tokens)"
    if est_tokens > DEFAULT_MAX_TOKENS:
        return False, f"too_long ({est_tokens} est tokens)"

    # Empty or near-empty after stripping
    stripped = content.strip()
    if len(stripped) < 20:
        return False, "near_empty"

    # Docs: skip if mostly URLs or links (low-quality scraped pages)
    if record.language == "md":
        url_chars = sum(len(m.group(0)) for m in re.finditer(r"https?://\S+", content))
        if len(content) > 100 and url_chars / len(content) > 0.5:
            return False, "mostly_urls"

    # Code: skip auto-generated files
    if record.language in ("rust", "ts", "js"):
        if "auto-generated" in content[:200].lower() or "do not edit" in content[:200].lower():
            return False, "auto_generated"

    return True, "pass"


def load_kenlm_model() -> object | None:
    """Load a pre-trained KenLM model for perplexity filtering."""
    try:
        import kenlm
    except ImportError:
        console.print("  [yellow]KenLM not installed — skipping perplexity filter[/yellow]")
        console.print("  [dim]Install: pip install https://github.com/kpu/kenlm/archive/master.zip[/dim]")
        return None

    # Try to load a pre-trained model
    model_path = PROJECT_ROOT / "models" / "kenlm" / "en_wikipedia.arpa"
    if not model_path.exists():
        # Try downloading from HuggingFace
        console.print("  [yellow]No KenLM model found. Download from huggingface.co/edugp/kenlm[/yellow]")
        console.print(f"  [dim]Expected at: {model_path}[/dim]")
        return None

    return kenlm.Model(str(model_path))


def compute_perplexity(model: object, text: str) -> float:
    """Compute per-word perplexity using KenLM."""
    score = model.score(text, bos=True, eos=True)
    words = len(text.split())
    if words == 0:
        return float("inf")
    return 10 ** (-score / words)


@app.command()
def filter_data(
    skip_rustfmt: bool = typer.Option(False, help="Skip rustfmt syntax checking"),
    skip_cargo: bool = typer.Option(True, help="Skip cargo check (slow, default: skip)"),
    enable_kenlm: bool = typer.Option(False, help="Enable KenLM perplexity filtering for docs"),
    perplexity_pct: float = typer.Option(95.0, help="Perplexity percentile cutoff (remove above)"),
    input_dir: Path = typer.Option(DEDUPED_DIR, help="Input directory"),
    output_dir: Path = typer.Option(FINAL_DIR, help="Output directory"),
):
    """Apply quality filters and Anchor version tagging."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load deduped data
    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    if not jsonl_files:
        console.print(f"[red]No JSONL files found in {input_dir}[/red]")
        raise typer.Exit(1)

    all_records: list[Record] = []
    for f in jsonl_files:
        all_records.extend(read_jsonl(f))

    total_before = len(all_records)
    console.print(f"[bold]Loaded {total_before} records for filtering[/bold]\n")

    # Setup optional components
    cargo_project = None
    if not skip_cargo:
        cargo_project = setup_cargo_project()

    kenlm_model = None
    if enable_kenlm:
        console.print("[bold]Loading KenLM model...[/bold]")
        kenlm_model = load_kenlm_model()

    # First pass: compute perplexity scores for docs if KenLM enabled
    doc_perplexities: dict[str, float] = {}
    if kenlm_model:
        console.print("[bold]Computing perplexity scores for docs...[/bold]")
        doc_records = [r for r in all_records if r.language == "md"]
        for r in track(doc_records, description="  Scoring docs"):
            doc_perplexities[r.id] = compute_perplexity(kenlm_model, r.content)

        if doc_perplexities:
            import statistics
            scores = sorted(doc_perplexities.values())
            cutoff_idx = int(len(scores) * perplexity_pct / 100)
            perplexity_cutoff = scores[min(cutoff_idx, len(scores) - 1)]
            console.print(f"  Perplexity cutoff ({perplexity_pct}th pct): {perplexity_cutoff:.1f}")
        else:
            perplexity_cutoff = float("inf")
    else:
        perplexity_cutoff = float("inf")

    kept: list[Record] = []
    rejected_reasons: dict[str, int] = {}
    modern_count = 0
    old_count = 0

    for record in track(all_records, description="Filtering"):
        # Quality heuristics
        passed, reason = quality_heuristics(record)
        if not passed:
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
            continue

        # KenLM perplexity filter for docs
        if kenlm_model and record.id in doc_perplexities:
            if doc_perplexities[record.id] > perplexity_cutoff:
                rejected_reasons["high_perplexity"] = rejected_reasons.get("high_perplexity", 0) + 1
                continue

        # Rust syntax check
        if record.language == "rust" and not skip_rustfmt:
            if is_likely_complete_rust(record.content) and not check_rustfmt(record.content):
                rejected_reasons["rustfmt_fail"] = rejected_reasons.get("rustfmt_fail", 0) + 1
                continue

        # cargo check (slow, opt-in)
        if record.language == "rust" and cargo_project and not skip_cargo:
            if is_likely_complete_rust(record.content) and not check_cargo(record.content, cargo_project):
                rejected_reasons["cargo_check_fail"] = rejected_reasons.get("cargo_check_fail", 0) + 1
                continue

        # Anchor version tagging enrichment
        if record.language == "rust":
            if is_modern_anchor(record.content):
                record.metadata["anchor_style"] = "modern"
                modern_count += 1
            elif "anchor_lang" in record.content or "declare_id!" in record.content:
                record.metadata["anchor_style"] = "legacy"
                old_count += 1

        kept.append(record)

    # Write filtered output
    out_path = output_dir / "filtered.jsonl"
    count = write_jsonl(kept, out_path)

    # Stats
    total_removed = total_before - count
    console.print(f"\n[bold green]Filtering complete:[/bold green]")
    console.print(f"  Before:  {total_before}")
    console.print(f"  After:   {count}")
    console.print(f"  Removed: {total_removed} ({total_removed / max(total_before, 1) * 100:.1f}%)")
    console.print(f"  Output:  {out_path}")

    if rejected_reasons:
        console.print(f"\n[bold]Rejection reasons:[/bold]")
        for reason, cnt in sorted(rejected_reasons.items(), key=lambda x: -x[1]):
            console.print(f"  {reason}: {cnt}")

    console.print(f"\n[bold]Anchor style breakdown:[/bold]")
    console.print(f"  Modern (0.30+): {modern_count}")
    console.print(f"  Legacy:         {old_count}")
    console.print(f"  Untagged:       {count - modern_count - old_count}")


def setup_cargo_project() -> Path:
    """Create a temporary Cargo project for type-checking."""
    tmpdir = Path(tempfile.mkdtemp(prefix="slm-cargo-"))
    (tmpdir / "src").mkdir()

    cargo_toml = tmpdir / "Cargo.toml"
    cargo_toml.write_text(
        '[package]\nname = "slm-check"\nversion = "0.1.0"\nedition = "2021"\n\n'
        "[dependencies]\n"
        'anchor-lang = "0.30"\n'
        'solana-program = "2.0"\n'
    )
    console.print(f"  [dim]Cargo project: {tmpdir}[/dim]")
    # Initial build to cache deps
    subprocess.run(
        ["cargo", "check"],
        cwd=str(tmpdir),
        capture_output=True,
        timeout=120,
    )
    return tmpdir


if __name__ == "__main__":
    app()
