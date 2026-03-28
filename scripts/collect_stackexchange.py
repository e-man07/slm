#!/usr/bin/env python3
"""Collect Solana Stack Exchange Q&A via the SE API.

IMPORTANT: Stack Exchange data is RAG-ONLY — the dump license explicitly
excludes LLM training since July 2024. We use the API for retrieval purposes.

API: api.stackexchange.com/2.3/
Rate limits: 300/day unauthenticated, 10,000/day with API key

Usage:
    python scripts/collect_stackexchange.py
    python scripts/collect_stackexchange.py --api-key YOUR_KEY --max-questions 5000
"""

from __future__ import annotations

import html
import re
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

SE_API = "https://api.stackexchange.com/2.3"
SITE = "solana"
PAGE_SIZE = 100
DELAY = 0.5  # Be respectful of rate limits


def strip_html_tags(text: str) -> str:
    """Strip HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@app.command()
def collect(
    api_key: str | None = typer.Option(None, envvar="SE_API_KEY", help="Stack Exchange API key"),
    max_questions: int = typer.Option(2000, help="Maximum questions to fetch"),
    min_score: int = typer.Option(1, help="Minimum question score"),
    min_answers: int = typer.Option(1, help="Minimum number of answers"),
):
    """Collect Solana SE Q&A pairs for RAG retrieval (NOT training)."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records: list[Record] = []
    page = 1
    has_more = True

    params = {
        "site": SITE,
        "pagesize": PAGE_SIZE,
        "sort": "votes",
        "order": "desc",
        "filter": "withbody",  # Include post bodies
        "min": str(min_score),
    }
    if api_key:
        params["key"] = api_key

    console.print(f"[bold]Fetching Solana SE questions (min score={min_score})...[/bold]")

    with httpx.Client(timeout=30) as client:
        while has_more and len(records) < max_questions:
            params["page"] = str(page)

            try:
                r = client.get(f"{SE_API}/questions", params=params)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                console.print(f"[red]API error: {e}[/red]")
                break

            questions = data.get("items", [])
            has_more = data.get("has_more", False)
            quota_remaining = data.get("quota_remaining", "?")

            if not questions:
                break

            for q in questions:
                if q.get("answer_count", 0) < min_answers:
                    continue

                q_title = q.get("title", "")
                q_body = strip_html_tags(q.get("body", ""))
                q_tags = q.get("tags", [])
                q_id = q["question_id"]

                # Fetch answers for this question
                try:
                    ans_r = client.get(
                        f"{SE_API}/questions/{q_id}/answers",
                        params={
                            "site": SITE,
                            "sort": "votes",
                            "order": "desc",
                            "filter": "withbody",
                            "pagesize": "5",
                            **({"key": api_key} if api_key else {}),
                        },
                    )
                    ans_r.raise_for_status()
                    answers = ans_r.json().get("items", [])
                except Exception:
                    answers = []

                if not answers:
                    time.sleep(DELAY)
                    continue

                # Build Q&A content
                parts = [
                    f"# {html.unescape(q_title)}",
                    f"Tags: {', '.join(q_tags)}",
                    f"\n## Question\n\n{q_body}",
                ]

                for i, a in enumerate(answers):
                    a_body = strip_html_tags(a.get("body", ""))
                    is_accepted = " ✓" if a.get("is_accepted") else ""
                    score = a.get("score", 0)
                    parts.append(f"\n## Answer {i + 1} (score: {score}{is_accepted})\n\n{a_body}")

                content = "\n".join(parts)

                record = Record(
                    id=Record.make_id(content),
                    source=f"stackexchange/{SITE}",
                    source_type="qa",
                    content=content,
                    language="md",
                    license="CC-BY-SA-4.0-no-training",
                    metadata={
                        "url": q.get("link", f"https://solana.stackexchange.com/q/{q_id}"),
                        "title": html.unescape(q_title),
                        "tags": q_tags,
                        "question_score": q.get("score", 0),
                        "answer_count": len(answers),
                        "collected_at": today_str(),
                        "training_permitted": "false",  # RAG-ONLY
                    },
                )
                records.append(record)

                time.sleep(DELAY)

            page += 1
            console.print(
                f"  [dim]Page {page - 1}: {len(records)} Q&A pairs, "
                f"quota remaining: {quota_remaining}[/dim]"
            )
            time.sleep(DELAY)

    if records:
        out_path = PROCESSED_DIR / "stackexchange-solana.jsonl"
        count = write_jsonl(records, out_path)
        console.print(f"\n[bold green]✓ {count} Q&A pairs → {out_path.name}[/bold green]")
        console.print("[yellow]⚠ These records are RAG-ONLY — excluded from training data[/yellow]")
    else:
        console.print("\n[yellow]No records extracted[/yellow]")


if __name__ == "__main__":
    app()
