#!/usr/bin/env python3
"""Discover open-source Solana/Anchor/Pinocchio repos on GitHub and collect training data.

Automatically searches GitHub for Solana program code, filters by license and quality,
then clones and processes repos using the same pipeline as collect_solana_code.py.

Usage:
    python scripts/discover_solana_repos.py                    # full discovery + collection
    python scripts/discover_solana_repos.py --discover-only    # just find repos, save list
    python scripts/discover_solana_repos.py --min-stars 10     # higher quality bar
    python scripts/discover_solana_repos.py --max-repos 500    # limit number of repos
    python scripts/discover_solana_repos.py --skip-clone       # use cached repos
    python scripts/discover_solana_repos.py --list             # show discovered repos
    python scripts/discover_solana_repos.py --refresh          # re-run GitHub search
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

# ---------------------------------------------------------------------------
# Ensure the scripts directory is importable
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).parent))

from collect_solana_code import (
    REPOS,
    SYSTEM_PROMPT,
    RepoSource,
    clone_repo,
    collect_rs_files,
    extract_code_units,
    generate_prompt_for_unit,
    make_sft_record,
    passes_quality_filter,
)

app = typer.Typer(invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "repos"
OUTPUT_DIR = PROJECT_ROOT / "data" / "collected"
OUTPUT_FILE = OUTPUT_DIR / "discovered_sft.jsonl"
CACHE_FILE = PROJECT_ROOT / "data" / "discovered_repos.json"

GITHUB_API = "https://api.github.com"

# Build the set of already-curated repos from collect_solana_code.py
KNOWN_REPOS: set[str] = {r.owner_repo.lower() for r in REPOS}

# Search queries targeting Solana program code
SEARCH_QUERIES = [
    'anchor_lang language:Rust',
    '"#[program]" language:Rust',
    'solana_program language:Rust',
    'pinocchio solana language:Rust',
    '"declare_id" anchor language:Rust',
    '"process_instruction" solana language:Rust',
]

ALLOWED_LICENSES = {"MIT", "Apache-2.0"}

# Patterns that indicate a directory contains Solana program code
_PROGRAM_DIR_PATTERNS = [
    "programs/",
    "program/src/",
    "src/lib.rs",
    "src/instructions/",
    "src/processor",
]


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _get_headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _handle_rate_limit(response: httpx.Response) -> None:
    """Sleep if we're close to hitting the rate limit."""
    remaining = int(response.headers.get("X-RateLimit-Remaining", "10"))
    if remaining <= 1:
        reset_ts = int(response.headers.get("X-RateLimit-Reset", "0"))
        wait = max(reset_ts - int(time.time()), 1) + 1
        console.print(f"  [yellow]Rate limit reached, sleeping {wait}s...[/yellow]")
        time.sleep(wait)
    elif remaining <= 5:
        time.sleep(2)


def search_repos(query: str, token: str, max_pages: int = 10) -> list[dict]:
    """Search GitHub repos with pagination and rate limit handling.

    Returns a list of raw repo dicts from the GitHub API.
    """
    repos: list[dict] = []
    headers = _get_headers(token)

    for page in range(1, max_pages + 1):
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 100,
            "page": page,
        }
        try:
            resp = httpx.get(
                f"{GITHUB_API}/search/repositories",
                params=params,
                headers=headers,
                timeout=30,
            )
        except httpx.HTTPError as exc:
            console.print(f"  [red]HTTP error during search: {exc}[/red]")
            break

        if resp.status_code == 403:
            # Rate limited — wait and retry this page
            _handle_rate_limit(resp)
            try:
                resp = httpx.get(
                    f"{GITHUB_API}/search/repositories",
                    params=params,
                    headers=headers,
                    timeout=30,
                )
            except httpx.HTTPError:
                break

        if resp.status_code != 200:
            console.print(
                f"  [red]Search API returned {resp.status_code}: "
                f"{resp.text[:200]}[/red]"
            )
            break

        data = resp.json()
        items = data.get("items", [])
        repos.extend(items)

        # Stop if we've exhausted results
        total = data.get("total_count", 0)
        if page * 100 >= min(total, 1000):
            break

        _handle_rate_limit(resp)
        # Mandatory delay between search requests (GitHub recommends 2s)
        time.sleep(2)

    return repos


def get_repo_tree(owner: str, repo: str, token: str) -> list[str]:
    """Get the file tree of a repo to auto-detect program directories.

    Returns a list of file paths in the repo.
    """
    headers = _get_headers(token)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/HEAD"

    try:
        resp = httpx.get(
            url,
            params={"recursive": "1"},
            headers=headers,
            timeout=30,
        )
    except httpx.HTTPError as exc:
        console.print(f"  [red]Tree API error for {owner}/{repo}: {exc}[/red]")
        return []

    if resp.status_code != 200:
        return []

    _handle_rate_limit(resp)

    tree = resp.json().get("tree", [])
    return [item["path"] for item in tree if item.get("type") in ("blob", "tree")]


def find_program_dirs(tree: list[str]) -> list[str]:
    """Find directories likely containing Solana program code.

    Examines file paths for patterns like programs/*/src/*.rs, program/src/*.rs,
    src/lib.rs, src/instructions/*.rs.

    Returns a list of subdirectory paths to collect from (relative to repo root).
    """
    dirs: set[str] = set()

    for path in tree:
        if not path.endswith(".rs"):
            continue

        # programs/<name>/src/*.rs -> programs/<name>
        if path.startswith("programs/"):
            parts = path.split("/")
            if len(parts) >= 3:
                dirs.add(f"programs/{parts[1]}")
            continue

        # program/src/*.rs -> program
        if path.startswith("program/src/"):
            dirs.add("program")
            continue

        # src/lib.rs or src/instructions/*.rs -> src
        if path.startswith("src/") and (
            "lib.rs" in path
            or "instructions/" in path
            or "processor" in path
            or "state/" in path
        ):
            dirs.add("src")
            continue

    return sorted(dirs)


# ---------------------------------------------------------------------------
# Discovery pipeline
# ---------------------------------------------------------------------------


def _repo_to_cache_dict(repo: dict) -> dict:
    """Convert a GitHub API repo dict to our lightweight cache format."""
    license_info = repo.get("license") or {}
    return {
        "full_name": repo["full_name"],
        "stars": repo.get("stargazers_count", 0),
        "license": license_info.get("spdx_id", "UNKNOWN"),
        "fork": repo.get("fork", False),
        "size": repo.get("size", 0),
        "description": repo.get("description") or "",
        "default_branch": repo.get("default_branch", "main"),
        "html_url": repo.get("html_url", ""),
        "subdirs": [],  # populated later by tree analysis
    }


def discover_repos(
    token: str,
    min_stars: int = 5,
    max_repos: int = 2000,
    tokens: list[str] | None = None,
) -> list[dict]:
    """Run all search queries and return deduplicated, filtered repo list."""
    seen: set[str] = set()
    candidates: list[dict] = []
    _tokens = tokens or ([token] if token else [""])

    for idx, query in enumerate(SEARCH_QUERIES):
        # Rotate tokens across queries to spread rate limits
        current_token = _tokens[idx % len(_tokens)]
        console.print(f"  Searching: [cyan]{query}[/cyan] (token {idx % len(_tokens) + 1})")
        raw = search_repos(query, current_token)
        console.print(f"    Found {len(raw)} results")

        for repo in raw:
            full_name = repo["full_name"].lower()
            if full_name in seen:
                continue
            seen.add(full_name)

            # Filter: skip known curated repos
            if full_name in KNOWN_REPOS:
                continue

            # Filter: skip forks
            if repo.get("fork", False):
                continue

            # Filter: license
            license_info = repo.get("license") or {}
            spdx = license_info.get("spdx_id", "")
            if spdx not in ALLOWED_LICENSES:
                continue

            # Filter: minimum stars
            stars = repo.get("stargazers_count", 0)
            if stars < min_stars:
                continue

            # Filter: skip tiny repos (< 1 KB as reported by API)
            if repo.get("size", 0) < 1:
                continue

            candidates.append(_repo_to_cache_dict(repo))

        # Be polite between search queries
        time.sleep(3)

    # Sort by stars descending, cap at max_repos
    candidates.sort(key=lambda r: r["stars"], reverse=True)
    if len(candidates) > max_repos:
        candidates = candidates[:max_repos]

    console.print(
        f"\n  [bold green]Discovered {len(candidates)} repos[/bold green] "
        f"(after dedup and filtering)"
    )
    return candidates


def detect_program_dirs(
    repos: list[dict], token: str, tokens: list[str] | None = None,
) -> list[dict]:
    """For each repo, use the Trees API to find program directories."""
    console.print("\n[bold blue]Auto-detecting program directories...[/bold blue]")
    _tokens = tokens or ([token] if token else [""])

    for idx, repo in enumerate(track(repos, description="Scanning trees...")):
        current_token = _tokens[idx % len(_tokens)]
        owner, name = repo["full_name"].split("/", 1)
        tree = get_repo_tree(owner, name, current_token)
        if tree:
            subdirs = find_program_dirs(tree)
            repo["subdirs"] = subdirs
        else:
            repo["subdirs"] = []
        # Small delay to stay within rate limits
        time.sleep(0.3)

    return repos


# ---------------------------------------------------------------------------
# Collection pipeline (reuses collect_solana_code.py functions)
# ---------------------------------------------------------------------------


def _repo_dict_to_source(repo: dict) -> RepoSource:
    """Convert a cached repo dict to a RepoSource for cloning and processing."""
    return RepoSource(
        owner_repo=repo["full_name"],
        subdirs=repo.get("subdirs", []),
        license=repo.get("license", "MIT"),
    )


def generate_file_prompt_discovered(file_path: Path, repo_source: RepoSource) -> str:
    """Generate a user prompt for a whole-file training example from a discovered repo."""
    repo_dir = RAW_DIR / repo_source.name
    try:
        rel = file_path.relative_to(repo_dir)
    except ValueError:
        rel = file_path.name
    parts = str(rel).split("/")

    if "instructions" in parts or "instruction" in parts:
        return (
            f"Write a complete Anchor instructions module for a Solana program "
            f"(from {repo_source.owner_repo}, file: {rel})."
        )
    if "state" in parts:
        return (
            f"Write the program state definitions for a Solana program "
            f"(from {repo_source.owner_repo}, file: {rel})."
        )
    if str(rel).endswith("lib.rs"):
        return (
            f"Write the main lib.rs entry point for a Solana Anchor program "
            f"(from {repo_source.owner_repo})."
        )

    stem = file_path.stem
    return (
        f"Write a complete Solana Rust module `{stem}` "
        f"(from {repo_source.owner_repo}, file: {rel})."
    )


def process_discovered_file(file_path: Path, repo_source: RepoSource) -> list[dict]:
    """Process one .rs file from a discovered repo and return SFT records."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if not passes_quality_filter(
        file_path, content, repo_owner_repo=repo_source.owner_repo
    ):
        return []

    records: list[dict] = []

    # 1. Whole-file example
    file_prompt = generate_file_prompt_discovered(file_path, repo_source)
    records.append(make_sft_record(SYSTEM_PROMPT, file_prompt, content.strip()))

    # 2. Code-unit examples
    units = extract_code_units(content)
    for unit in units:
        prompt = generate_prompt_for_unit(unit, repo_source.owner_repo)
        records.append(make_sft_record(SYSTEM_PROMPT, prompt, unit.code))

    return records


def collect_from_repos(
    repos: list[dict],
    skip_clone: bool = False,
) -> list[dict]:
    """Clone discovered repos and extract SFT training records."""
    all_records: list[dict] = []
    total_files = 0
    total_units = 0
    cloned = 0
    failed = 0

    for repo_dict in track(repos, description="Processing repos..."):
        source = _repo_dict_to_source(repo_dict)
        repo_path = RAW_DIR / source.name

        # Clone if needed
        if not skip_clone:
            clone_repo(source)

        if not repo_path.exists():
            failed += 1
            continue
        cloned += 1

        # Collect .rs files
        rs_files = collect_rs_files(repo_path, source.subdirs)

        for fpath in rs_files:
            records = process_discovered_file(fpath, source)
            if records:
                total_files += 1
                total_units += len(records) - 1
                all_records.extend(records)

    console.print(f"\n  Repos cloned/found: {cloned}, failed: {failed}")
    console.print(f"  Files processed: {total_files}")
    console.print(f"  Code unit examples: {total_units}")
    console.print(f"  Total SFT records: {len(all_records)}")

    return all_records


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def save_cache(repos: list[dict]) -> None:
    """Save discovered repos to JSON cache."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(repos, f, indent=2, ensure_ascii=False)
    console.print(f"  Cache saved: {CACHE_FILE} ({len(repos)} repos)")


def load_cache() -> list[dict] | None:
    """Load discovered repos from JSON cache, or None if missing."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            repos = json.load(f)
        console.print(f"  [dim]Loaded {len(repos)} repos from cache[/dim]")
        return repos
    except (json.JSONDecodeError, OSError) as exc:
        console.print(f"  [yellow]Failed to load cache: {exc}[/yellow]")
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    discover_only: bool = typer.Option(
        False, "--discover-only", help="Only discover repos, don't clone or collect"
    ),
    min_stars: int = typer.Option(
        5, "--min-stars", help="Minimum star count for discovered repos"
    ),
    max_repos: int = typer.Option(
        2000, "--max-repos", help="Maximum number of repos to process"
    ),
    skip_clone: bool = typer.Option(
        False, "--skip-clone", help="Skip cloning, reuse existing clones"
    ),
    list_repos: bool = typer.Option(
        False, "--list", help="Show discovered repos and exit"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="Force re-discovery even if cache exists"
    ),
):
    """Discover Solana repos on GitHub and collect SFT training data."""
    # Support multiple tokens via GITHUB_TOKEN and GITHUB_TOKEN_2 for faster rate limits
    tokens = []
    for var in ("GITHUB_TOKEN", "GITHUB_TOKEN_2"):
        t = os.environ.get(var, "")
        if t:
            tokens.append(t)
    token = tokens[0] if tokens else ""
    if not token:
        console.print(
            "[yellow]Warning: GITHUB_TOKEN not set. "
            "API rate limits will be very low (10 req/min).[/yellow]\n"
            "Set it with: export GITHUB_TOKEN=ghp_...\n"
        )
    elif len(tokens) > 1:
        console.print(f"[green]Using {len(tokens)} GitHub tokens for faster rate limits[/green]\n")

    # --- List mode ---
    if list_repos:
        repos = load_cache()
        if repos is None:
            console.print("[red]No cache found. Run discovery first.[/red]")
            raise typer.Exit(1)

        table = Table(title=f"Discovered Repos ({len(repos)})")
        table.add_column("Repo", style="cyan", no_wrap=True)
        table.add_column("Stars", justify="right")
        table.add_column("License")
        table.add_column("Subdirs")

        for r in repos[:100]:
            subdirs = ", ".join(r.get("subdirs", [])) or "(whole repo)"
            table.add_row(
                r["full_name"],
                str(r["stars"]),
                r.get("license", "?"),
                subdirs[:60],
            )
        console.print(table)
        if len(repos) > 100:
            console.print(f"  ... and {len(repos) - 100} more")
        raise typer.Exit()

    # --- Discovery phase ---
    repos = None
    if not refresh:
        repos = load_cache()

    if repos is None:
        console.print("\n[bold blue]Phase 1: Discovering repos on GitHub[/bold blue]")
        repos = discover_repos(token, min_stars=min_stars, max_repos=max_repos, tokens=tokens)

        console.print("\n[bold blue]Phase 2: Detecting program directories[/bold blue]")
        repos = detect_program_dirs(repos, token, tokens=tokens)

        save_cache(repos)

    if discover_only:
        console.print("\n[bold green]Discovery complete.[/bold green]")
        console.print(f"  Repos found: {len(repos)}")
        console.print(f"  Cache: {CACHE_FILE}")
        raise typer.Exit()

    # --- Apply max_repos cap (cache may have more) ---
    if len(repos) > max_repos:
        repos = repos[:max_repos]
        console.print(f"  [dim]Capped to {max_repos} repos[/dim]")

    # --- Collection phase ---
    console.print(
        f"\n[bold blue]Phase 3: Cloning and collecting from "
        f"{len(repos)} repos[/bold blue]"
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_records = collect_from_repos(repos, skip_clone=skip_clone)

    if not all_records:
        console.print("[yellow]No SFT records generated.[/yellow]")
        raise typer.Exit()

    # --- Write output ---
    console.print(f"\n[bold blue]Phase 4: Writing output[/bold blue]")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    console.print(f"\n[bold green]Done![/bold green] Output: {OUTPUT_FILE}")
    console.print(f"  Total SFT records: {len(all_records)}")
    console.print(
        f"  File size: {OUTPUT_FILE.stat().st_size / 1_048_576:.1f} MB"
    )


if __name__ == "__main__":
    app()
