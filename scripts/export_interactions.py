"""Export user interactions from Postgres to JSONL for SFT/DPO retraining.

Usage:
    python scripts/export_interactions.py --output data/collected/
    python scripts/export_interactions.py --output data/collected/ --since 2026-04-01
    python scripts/export_interactions.py --output data/collected/ --source mcp
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

try:
    import psycopg2
except ImportError:
    print("pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)


SYSTEM_PROMPT = "You are Sealevel, an expert Solana and Anchor developer..."


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Set DATABASE_URL environment variable", file=sys.stderr)
        sys.exit(1)
    return psycopg2.connect(url)


def fetch_interactions(conn, since=None, source=None, min_response_len=50):
    """Fetch interactions from consenting users."""
    query = """
        SELECT i.id, i.source, i.prompt_messages, i.response,
               i.prompt_tokens, i.completion_tokens, i.total_tokens,
               i.rag_context, i.created_at,
               f.signal as feedback
        FROM interactions i
        JOIN users u ON i.user_id = u.id AND u.training_consent = true
        LEFT JOIN feedback f ON f.interaction_id = i.id
        WHERE LENGTH(i.response) >= %s
    """
    params = [min_response_len]

    if since:
        query += " AND i.created_at >= %s"
        params.append(since)
    if source:
        query += " AND i.source = %s"
        params.append(source)

    query += " ORDER BY i.created_at ASC"

    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def deduplicate(interactions):
    """Deduplicate by prompt content hash."""
    seen = set()
    unique = []
    for row in interactions:
        prompt_hash = hashlib.sha256(row["prompt_messages"].encode()).hexdigest()[:16]
        if prompt_hash not in seen:
            seen.add(prompt_hash)
            unique.append(row)
    return unique


def export_sft(interactions, output_path):
    """Export as SFT training data (ChatML messages format)."""
    path = os.path.join(output_path, "sft_interactions.jsonl")
    count = 0
    with open(path, "w") as f:
        for row in interactions:
            try:
                prompt_msgs = json.loads(row["prompt_messages"])
            except json.JSONDecodeError:
                continue

            # Build messages array: prompt messages + assistant response
            messages = []
            for msg in prompt_msgs:
                if msg.get("role") == "system":
                    continue  # Skip system prompt (added during training)
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "assistant", "content": row["response"]})

            if len(messages) < 2:
                continue

            f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
            count += 1

    print(f"SFT: {count} records → {path}")
    return count


def export_dpo(interactions, output_path):
    """Export feedback interactions as DPO training pairs."""
    chosen_path = os.path.join(output_path, "dpo_chosen.jsonl")
    rejected_path = os.path.join(output_path, "dpo_rejected.jsonl")

    chosen_count = 0
    rejected_count = 0

    with open(chosen_path, "w") as f_chosen, open(rejected_path, "w") as f_rejected:
        for row in interactions:
            if not row.get("feedback"):
                continue

            try:
                prompt_msgs = json.loads(row["prompt_messages"])
            except json.JSONDecodeError:
                continue

            messages = [m for m in prompt_msgs if m.get("role") != "system"]
            messages.append({"role": "assistant", "content": row["response"]})

            record = json.dumps({"messages": messages}, ensure_ascii=False) + "\n"

            if row["feedback"] == "up":
                f_chosen.write(record)
                chosen_count += 1
            elif row["feedback"] == "down":
                f_rejected.write(record)
                rejected_count += 1

    print(f"DPO chosen: {chosen_count} → {chosen_path}")
    print(f"DPO rejected: {rejected_count} → {rejected_path}")
    return chosen_count, rejected_count


def main():
    parser = argparse.ArgumentParser(description="Export interactions for retraining")
    parser.add_argument("--output", default="data/collected", help="Output directory")
    parser.add_argument("--since", help="Only export after this date (YYYY-MM-DD)")
    parser.add_argument("--source", choices=["web", "mcp", "cli"], help="Filter by source")
    parser.add_argument("--min-length", type=int, default=50, help="Min response length")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    since = datetime.fromisoformat(args.since) if args.since else None

    conn = connect()
    try:
        rows = fetch_interactions(conn, since=since, source=args.source, min_response_len=args.min_length)
        print(f"Fetched {len(rows)} interactions (consent=true)")

        unique = deduplicate(rows)
        print(f"After dedup: {len(unique)}")

        export_sft(unique, args.output)
        export_dpo(unique, args.output)

        # Summary
        sources = {}
        for r in unique:
            sources[r["source"]] = sources.get(r["source"], 0) + 1
        print(f"By source: {sources}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
