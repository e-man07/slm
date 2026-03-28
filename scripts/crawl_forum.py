#!/usr/bin/env python3
"""Crawl forum.solana.com via the Discourse API.

Discourse API is public and rate-limited. We fetch topics and their posts,
extracting high-quality Q&A content. RAG-only by default (license unclear).

Usage:
    python scripts/crawl_forum.py
    python scripts/crawl_forum.py --max-topics 500
    python scripts/crawl_forum.py --category-id 7    # specific category
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import typer
from rich.console import Console

from schema import Record, today_str, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

FORUM_BASE = "https://forum.solana.com"
# Rate limit: be respectful, 1 req/sec
DELAY = 1.0


def fetch_json(client: httpx.Client, path: str) -> dict | None:
    """Fetch JSON from forum API."""
    url = f"{FORUM_BASE}/{path}"
    try:
        r = client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, Exception) as e:
        console.print(f"  [dim]Failed: {path} — {e}[/dim]")
        return None


def strip_html(html: str) -> str:
    """Basic HTML tag stripping for Discourse post content."""
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", html)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@app.command()
def crawl_forum(
    max_topics: int = typer.Option(1000, help="Maximum topics to fetch"),
    min_posts: int = typer.Option(2, help="Minimum posts per topic (skip unanswered)"),
    category_id: int | None = typer.Option(None, help="Filter to specific category ID"),
):
    """Crawl forum.solana.com and extract Q&A content."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records: list[Record] = []
    page = 0

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        # Fetch topic listings
        console.print("[bold]Fetching topic listings...[/bold]")
        topic_ids: list[int] = []

        while len(topic_ids) < max_topics:
            path = f"latest.json?page={page}"
            if category_id:
                path = f"c/{category_id}.json?page={page}"

            data = fetch_json(client, path)
            if not data:
                break

            topics = data.get("topic_list", {}).get("topics", [])
            if not topics:
                break

            for t in topics:
                if t.get("posts_count", 0) >= min_posts:
                    topic_ids.append(t["id"])

            page += 1
            time.sleep(DELAY)
            console.print(f"  [dim]Page {page}: {len(topic_ids)} topics so far[/dim]")

        console.print(f"\n[bold]Fetching {len(topic_ids)} topics...[/bold]")

        for i, topic_id in enumerate(topic_ids[:max_topics]):
            data = fetch_json(client, f"t/{topic_id}.json")
            if not data:
                time.sleep(DELAY)
                continue

            title = data.get("title", "")
            posts = data.get("post_stream", {}).get("posts", [])

            if len(posts) < min_posts:
                time.sleep(DELAY)
                continue

            # Build Q&A content: first post = question, rest = answers
            parts = [f"# {title}\n"]
            for post in posts:
                username = post.get("username", "unknown")
                cooked = post.get("cooked", "")
                text = strip_html(cooked)
                if not text:
                    continue
                role = "Question" if post.get("post_number") == 1 else "Answer"
                parts.append(f"## {role} (by {username})\n\n{text}\n")

            content = "\n".join(parts)
            if len(content) < 200:
                time.sleep(DELAY)
                continue

            slug = data.get("slug", str(topic_id))
            record = Record(
                id=Record.make_id(content),
                source="forum/forum.solana.com",
                source_type="qa",
                content=content,
                language="md",
                license="unknown",
                metadata={
                    "url": f"{FORUM_BASE}/t/{slug}/{topic_id}",
                    "title": title,
                    "posts_count": len(posts),
                    "collected_at": today_str(),
                    "training_permitted": "false",  # RAG-only until license clarified
                },
            )
            records.append(record)

            if (i + 1) % 50 == 0:
                console.print(f"  [dim]{i + 1}/{len(topic_ids)} topics processed[/dim]")

            time.sleep(DELAY)

    if records:
        out_path = PROCESSED_DIR / "forum-solana.jsonl"
        count = write_jsonl(records, out_path)
        console.print(f"\n[bold green]✓ {count} forum Q&A records → {out_path.name}[/bold green]")
    else:
        console.print("\n[yellow]No forum records extracted[/yellow]")


if __name__ == "__main__":
    app()
