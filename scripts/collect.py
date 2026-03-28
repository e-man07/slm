#!/usr/bin/env python3
"""Stage 1: Collect data from GitHub repos and normalize to JSONL.

Usage:
    python scripts/collect.py                    # collect all repos
    python scripts/collect.py --source anchor    # collect single repo
    python scripts/collect.py --list             # list configured sources
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import tomllib
import typer
from rich.console import Console
from rich.progress import track

from schema import (
    SKIP_PATTERNS,
    Record,
    detect_anchor_version,
    detect_language,
    today_str,
    write_jsonl,
)

app = typer.Typer(invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIG_PATH = PROJECT_ROOT / "configs" / "sources.toml"

# Min file size to collect (bytes) — skip trivially small files
MIN_FILE_SIZE = 50
# Max file size (bytes) — skip huge generated files
MAX_FILE_SIZE = 500_000


def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


def clone_repo(name: str, url: str) -> Path:
    """Clone a repo at depth 1. Returns the clone path."""
    dest = RAW_DIR / name
    if dest.exists():
        console.print(f"  [dim]Already cloned: {name}, pulling latest...[/dim]")
        subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only"],
            capture_output=True,
        )
        return dest

    console.print(f"  Cloning {url}...")
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"  [red]Failed to clone {name}: {result.stderr}[/red]")
        raise typer.Exit(1)
    return dest


def find_cargo_toml_versions(repo_path: Path) -> dict[str, str]:
    """Scan repo for Cargo.toml files and extract anchor-lang versions.

    Returns a mapping of directory path -> anchor version.
    """
    versions = {}
    for cargo_toml in repo_path.rglob("Cargo.toml"):
        try:
            content = cargo_toml.read_text(encoding="utf-8", errors="replace")
            version = detect_anchor_version(content)
            if version:
                versions[str(cargo_toml.parent)] = version
        except OSError:
            continue
    return versions


def find_closest_anchor_version(file_path: Path, versions: dict[str, str]) -> str | None:
    """Find the anchor version from the nearest parent Cargo.toml."""
    path_str = str(file_path.parent)
    # Walk up directories to find the closest Cargo.toml with anchor version
    while path_str:
        if path_str in versions:
            return versions[path_str]
        parent = str(Path(path_str).parent)
        if parent == path_str:
            break
        path_str = parent
    return None


def should_skip(path: Path) -> bool:
    """Check if file/directory should be skipped."""
    parts = set(path.parts)
    return bool(parts & SKIP_PATTERNS)


def process_repo(name: str, config: dict) -> list[Record]:
    """Process a cloned repo into Records."""
    repo_path = RAW_DIR / name
    if not repo_path.exists():
        return []

    url = config["url"]
    license_id = config["license"]
    allowed_langs = set(config.get("languages", ["rust", "ts", "md"]))

    # Pre-scan for anchor versions
    anchor_versions = find_cargo_toml_versions(repo_path)

    records = []
    files = [
        f
        for f in repo_path.rglob("*")
        if f.is_file() and not should_skip(f) and detect_language(f) in allowed_langs
    ]

    for file_path in files:
        # Size filter
        size = file_path.stat().st_size
        if size < MIN_FILE_SIZE or size > MAX_FILE_SIZE:
            continue

        lang = detect_language(file_path)
        if not lang:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Build relative path for metadata
        rel_path = str(file_path.relative_to(repo_path))

        metadata = {
            "file_path": rel_path,
            "collected_at": today_str(),
        }

        # Add anchor version if found
        anchor_ver = find_closest_anchor_version(file_path, anchor_versions)
        if anchor_ver:
            metadata["anchor_version"] = anchor_ver

        source = f"github/{url.split('github.com/')[-1]}"

        record = Record(
            id=Record.make_id(content),
            source=source,
            source_type="code" if lang in ("rust", "ts", "js") else "docs",
            content=content,
            language=lang,
            license=license_id,
            metadata=metadata,
        )
        records.append(record)

    return records


@app.callback(invoke_without_command=True)
def collect(
    ctx: typer.Context,
    source: str | None = typer.Option(None, help="Collect a single source by name"),
    list_sources: bool = typer.Option(False, "--list", help="List configured sources"),
):
    """Collect data from configured sources and normalize to JSONL."""
    if ctx.invoked_subcommand is not None:
        return
    config = load_config()

    if list_sources:
        console.print("\n[bold]Configured repo sources:[/bold]")
        for name, cfg in config.get("repos", {}).items():
            permitted = "✅" if cfg.get("training_permitted") else "❌"
            console.print(f"  {permitted} {name}: {cfg['url']}")
        console.print("\n[bold]Configured dataset sources:[/bold]")
        for name, cfg in config.get("datasets", {}).items():
            permitted = {"true": "✅", "false": "❌"}.get(
                str(cfg.get("training_permitted", "pending")).lower(), "⚠️"
            )
            console.print(f"  {permitted} {name}: {cfg['url']}")
        console.print("\n[bold]Excluded sources:[/bold]")
        for name, cfg in config.get("excluded", {}).items():
            console.print(f"  ❌ {name}: {cfg.get('reason', 'N/A')}")
        raise typer.Exit()

    repos = config.get("repos", {})
    if source:
        if source not in repos:
            console.print(f"[red]Unknown source: {source}[/red]")
            console.print(f"Available: {', '.join(repos.keys())}")
            raise typer.Exit(1)
        repos = {source: repos[source]}

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    total_records = 0
    for name, cfg in repos.items():
        console.print(f"\n[bold blue]Processing: {name}[/bold blue]")

        if not cfg.get("training_permitted", False):
            console.print(f"  [yellow]Skipping {name} — training not permitted[/yellow]")
            continue

        # Clone
        clone_repo(name, cfg["url"])

        # Process
        records = process_repo(name, cfg)

        if records:
            out_path = PROCESSED_DIR / f"{name}.jsonl"
            count = write_jsonl(records, out_path)
            console.print(f"  [green]✓ {count} records → {out_path.name}[/green]")
            total_records += count
        else:
            console.print(f"  [yellow]No records extracted[/yellow]")

    console.print(f"\n[bold green]Collection complete: {total_records} total records[/bold green]")


@app.command()
def collect_hf_datasets():
    """Download and normalize HuggingFace datasets to JSONL."""
    try:
        from datasets import load_dataset
    except ImportError:
        console.print("[red]Install datasets: pip install datasets[/red]")
        raise typer.Exit(1)

    config = load_config()
    datasets_config = config.get("datasets", {})

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for name, cfg in datasets_config.items():
        console.print(f"\n[bold blue]Downloading: {name}[/bold blue]")

        hf_id = cfg["url"]
        license_id = cfg.get("license", "check-hf-card")
        permitted = str(cfg.get("training_permitted", "pending")).lower()

        try:
            ds = load_dataset(hf_id, split="train")
        except Exception as e:
            console.print(f"  [red]Failed: {e}[/red]")
            continue

        records = []
        columns = ds.column_names

        for row in track(ds, description=f"  Processing {name}"):
            # Try to extract content from common column patterns
            content = None
            if "messages" in columns:
                # ChatML format — serialize the conversation
                content = json.dumps(row["messages"], ensure_ascii=False)
                source_type = "qa"
            elif "instruction" in columns:
                # Alpaca format
                parts = [row.get("instruction", "")]
                if row.get("input"):
                    parts.append(row["input"])
                if row.get("output"):
                    parts.append(row["output"])
                content = "\n\n".join(parts)
                source_type = "qa"
            elif "text" in columns:
                content = row["text"]
                source_type = "docs"
            elif "content" in columns:
                content = row["content"]
                source_type = "docs"
            else:
                # Fallback: serialize JSON-safe fields only
                safe = {}
                for k in columns:
                    v = row[k]
                    if isinstance(v, (str, int, float, bool, type(None), list, dict)):
                        safe[k] = v
                content = json.dumps(safe, ensure_ascii=False) if safe else None
                source_type = "qa"

            if not content or len(content.strip()) < 50:
                continue

            record = Record(
                id=Record.make_id(content),
                source=f"huggingface/{hf_id}",
                source_type=source_type,
                content=content,
                language="md",  # Most HF datasets are natural language
                license=license_id,
                metadata={
                    "collected_at": today_str(),
                    "training_permitted": permitted,
                },
            )
            records.append(record)

        if records:
            out_path = PROCESSED_DIR / f"hf-{name}.jsonl"
            count = write_jsonl(records, out_path)
            console.print(f"  [green]✓ {count} records → {out_path.name}[/green]")
        else:
            console.print(f"  [yellow]No records extracted[/yellow]")


if __name__ == "__main__":
    app()
