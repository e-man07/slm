#!/usr/bin/env python3
"""Crawl documentation sites using Playwright + trafilatura.

Targets (from research doc):
- docs.rs/anchor-lang/latest (Anchor Rust API)
- helius.dev/blog (technical articles — RAG-only until permission)
- helius.dev/docs (API docs — RAG-only until permission)
- developers.metaplex.com (Metaplex docs — RAG-only until permission)

Usage:
    python scripts/crawl_docs.py                     # crawl all configured sites
    python scripts/crawl_docs.py --site anchor-rustdoc
    python scripts/crawl_docs.py --install           # install playwright browsers
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import typer
from rich.console import Console
from rich.progress import track

from schema import Record, today_str, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Crawl configs: name -> {start_url, allowed_prefix, license, training_permitted, max_pages}
CRAWL_TARGETS = {
    "anchor-rustdoc": {
        "start_urls": ["https://docs.rs/anchor-lang/0.30.1/anchor_lang/"],
        "allowed_prefix": "https://docs.rs/anchor-lang/0.30.1/",
        "license": "Apache-2.0",
        "training_permitted": True,
        "max_pages": 500,
        "description": "Anchor Rust API reference (v0.30.1 — latest with working docs)",
        "extract_mode": "rustdoc",
    },
    "anchor-docs": {
        "start_urls": ["https://www.anchor-lang.com/docs"],
        "allowed_prefix": "https://www.anchor-lang.com/docs",
        "license": "Apache-2.0",
        "training_permitted": True,
        "max_pages": 100,
        "description": "Official Anchor guides and tutorials",
    },
    "helius-blog": {
        "start_urls": ["https://www.helius.dev/blog"],
        "allowed_prefix": "https://www.helius.dev/blog",
        "license": "unknown",
        "training_permitted": False,
        "max_pages": 200,
        "description": "Helius technical blog (RAG-only)",
    },
    "helius-docs": {
        "start_urls": ["https://docs.helius.dev/"],
        "allowed_prefix": "https://docs.helius.dev/",
        "license": "unknown",
        "training_permitted": False,
        "max_pages": 300,
        "description": "Helius API documentation (RAG-only)",
    },
    "metaplex-docs": {
        "start_urls": ["https://developers.metaplex.com/"],
        "allowed_prefix": "https://developers.metaplex.com/",
        "license": "unknown",
        "training_permitted": False,
        "max_pages": 300,
        "description": "Metaplex developer docs (RAG-only)",
    },
}


def extract_text(html: str, extract_mode: str = "default") -> str:
    """Extract clean text from HTML using trafilatura."""
    try:
        import trafilatura

        if extract_mode == "rustdoc":
            # Rustdoc pages have structured API docs — use recall mode to capture more
            result = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
                include_links=True,
                output_format="txt",
            )
        else:
            result = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
                output_format="txt",
            )
        return result or ""
    except ImportError:
        console.print("[red]Install trafilatura: pip install trafilatura[/red]")
        raise typer.Exit(1)


def extract_links(html: str, base_url: str, allowed_prefix: str) -> list[str]:
    """Extract same-domain links from HTML."""
    links = set()
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = match.group(1)
        # Skip anchors, javascript, mailto
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        full_url = urljoin(base_url, href)
        # Strip fragment
        full_url = full_url.split("#")[0]
        # Only follow links within allowed prefix
        if full_url.startswith(allowed_prefix):
            links.add(full_url)
    return list(links)


def crawl_site(
    name: str,
    config: dict,
    delay: float = 1.0,
) -> list[Record]:
    """Crawl a site using Playwright, extract text with trafilatura."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        console.print("[red]Install playwright: pip install playwright && playwright install chromium[/red]")
        raise typer.Exit(1)

    start_urls = config["start_urls"]
    allowed_prefix = config["allowed_prefix"]
    max_pages = config["max_pages"]
    license_id = config["license"]
    training_permitted = config["training_permitted"]
    extract_mode = config.get("extract_mode", "default")

    visited: set[str] = set()
    queue: list[str] = list(start_urls)
    records: list[Record] = []

    console.print(f"  Starting crawl of {allowed_prefix} (max {max_pages} pages)")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(15000)

        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                # Wait for dynamic content (JS-heavy sites need more time)
                page.wait_for_timeout(2000)
                html = page.content()
            except Exception as e:
                console.print(f"  [dim]Skip {url}: {e}[/dim]")
                continue

            # Extract text
            text = extract_text(html, extract_mode=extract_mode)
            if not text or len(text.strip()) < 100:
                continue

            # Extract and queue new links
            new_links = extract_links(html, url, allowed_prefix)
            for link in new_links:
                if link not in visited:
                    queue.append(link)

            record = Record(
                id=Record.make_id(text),
                source=f"crawl/{name}",
                source_type="docs",
                content=text,
                language="md",
                license=license_id,
                metadata={
                    "url": url,
                    "collected_at": today_str(),
                    "training_permitted": str(training_permitted).lower(),
                },
            )
            records.append(record)

            if len(records) % 10 == 0:
                console.print(f"  [dim]{len(records)} pages crawled, {len(queue)} in queue[/dim]")

            time.sleep(delay)

        browser.close()

    return records


@app.command()
def crawl(
    site: str | None = typer.Option(None, help="Crawl a single site by name"),
    delay: float = typer.Option(1.0, help="Delay between requests in seconds"),
    list_sites: bool = typer.Option(False, "--list", help="List configured crawl targets"),
    install: bool = typer.Option(False, help="Install Playwright browsers"),
):
    """Crawl documentation sites and extract clean text."""
    if install:
        import subprocess

        subprocess.run(["playwright", "install", "chromium"], check=True)
        raise typer.Exit()

    if list_sites:
        console.print("\n[bold]Configured crawl targets:[/bold]")
        for name, cfg in CRAWL_TARGETS.items():
            permitted = "✅" if cfg["training_permitted"] else "🔍 RAG-only"
            console.print(f"  {permitted} {name}: {cfg['description']}")
            console.print(f"       {cfg['start_urls'][0]} (max {cfg['max_pages']} pages)")
        raise typer.Exit()

    targets = CRAWL_TARGETS
    if site:
        if site not in targets:
            console.print(f"[red]Unknown site: {site}. Available: {', '.join(targets.keys())}[/red]")
            raise typer.Exit(1)
        targets = {site: targets[site]}

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    total = 0
    for name, cfg in targets.items():
        console.print(f"\n[bold blue]Crawling: {name}[/bold blue] ({cfg['description']})")
        records = crawl_site(name, cfg, delay=delay)

        if records:
            out_path = PROCESSED_DIR / f"crawl-{name}.jsonl"
            count = write_jsonl(records, out_path)
            console.print(f"  [green]✓ {count} pages → {out_path.name}[/green]")
            total += count
        else:
            console.print(f"  [yellow]No content extracted[/yellow]")

    console.print(f"\n[bold green]Crawl complete: {total} total pages[/bold green]")


if __name__ == "__main__":
    app()
