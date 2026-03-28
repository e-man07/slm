#!/usr/bin/env python3
"""Collect on-chain Solana data via Helius API.

Sources:
- Enhanced transaction data (parsed, human-readable)
- Anchor IDLs from on-chain programs
- Program metadata from OtterSec verification API

Requires: HELIUS_API_KEY env var or --api-key flag
Free tier: 1M credits/month at 10 RPS

Usage:
    python scripts/collect_onchain.py idls           # fetch popular program IDLs
    python scripts/collect_onchain.py transactions    # fetch example transactions
"""

from __future__ import annotations

import json
import os
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

# Well-known Solana programs to fetch IDLs for
KNOWN_PROGRAMS = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "SPL Token",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "Token-2022 (Extensions)",
    "11111111111111111111111111111111": "System Program",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "Associated Token Account",
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s": "Metaplex Token Metadata",
    "ComputeBudget111111111111111111111111111111": "Compute Budget",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter v6",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM",
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": "Serum DEX v3",
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY": "Phoenix DEX",
    "MangoeXrGctt9zFUWTdPVqJePGXjTG6TaKnS3EafLhZ": "Mango Markets v4",
}

DELAY = 0.15  # ~7 RPS, under the 10 RPS limit


def get_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get("HELIUS_API_KEY")
    if not key:
        console.print("[red]Set HELIUS_API_KEY env var or pass --api-key[/red]")
        console.print("Sign up free at https://dashboard.helius.dev/signup")
        raise typer.Exit(1)
    return key


@app.command()
def idls(
    api_key: str | None = typer.Option(None, envvar="HELIUS_API_KEY", help="Helius API key"),
):
    """Fetch Anchor IDLs for well-known Solana programs."""
    key = get_api_key(api_key)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records: list[Record] = []

    console.print("[bold]Fetching Anchor IDLs for known programs...[/bold]")

    with httpx.Client(timeout=30) as client:
        for program_id, name in KNOWN_PROGRAMS.items():
            console.print(f"  {name} ({program_id[:8]}...)")

            # Try Helius enhanced API for program metadata
            try:
                r = client.post(
                    f"https://mainnet.helius-rpc.com/?api-key={key}",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getAccountInfo",
                        "params": [program_id, {"encoding": "base64"}],
                    },
                )
                r.raise_for_status()
                account_data = r.json()
            except Exception as e:
                console.print(f"    [dim]Skip: {e}[/dim]")
                time.sleep(DELAY)
                continue

            # Try OtterSec verification API for IDL
            try:
                r = client.get(
                    f"https://verify.osec.io/status-all/{program_id}",
                    timeout=10,
                )
                if r.status_code == 200:
                    verify_data = r.json()
                    idl_content = json.dumps(verify_data, indent=2)

                    record = Record(
                        id=Record.make_id(idl_content),
                        source=f"onchain/osec-verify/{program_id}",
                        source_type="code",
                        content=idl_content,
                        language="json",
                        license="Apache-2.0",
                        metadata={
                            "program_id": program_id,
                            "program_name": name,
                            "source_api": "osec-verify",
                            "collected_at": today_str(),
                        },
                    )
                    records.append(record)
                    console.print(f"    [green]✓ OtterSec verification data[/green]")
            except Exception:
                pass

            time.sleep(DELAY)

    if records:
        out_path = PROCESSED_DIR / "onchain-idls.jsonl"
        count = write_jsonl(records, out_path)
        console.print(f"\n[bold green]✓ {count} IDL records → {out_path.name}[/bold green]")
    else:
        console.print("\n[yellow]No IDL records extracted[/yellow]")


@app.command()
def transactions(
    api_key: str | None = typer.Option(None, envvar="HELIUS_API_KEY", help="Helius API key"),
    max_per_program: int = typer.Option(10, help="Max transactions per program"),
):
    """Fetch enhanced transaction examples from Helius for known programs."""
    key = get_api_key(api_key)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    records: list[Record] = []
    # Use a subset of programs for transaction examples
    target_programs = {
        k: v
        for k, v in list(KNOWN_PROGRAMS.items())[:6]
    }

    console.print("[bold]Fetching enhanced transactions...[/bold]")

    with httpx.Client(timeout=30) as client:
        for program_id, name in target_programs.items():
            console.print(f"  {name}")

            # Get recent transaction signatures for this program
            try:
                r = client.post(
                    f"https://mainnet.helius-rpc.com/?api-key={key}",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignaturesForAddress",
                        "params": [program_id, {"limit": max_per_program}],
                    },
                )
                r.raise_for_status()
                sigs_data = r.json().get("result", [])
                signatures = [s["signature"] for s in sigs_data if s.get("signature")]
            except Exception as e:
                console.print(f"    [dim]Skip signatures: {e}[/dim]")
                time.sleep(DELAY)
                continue

            if not signatures:
                time.sleep(DELAY)
                continue

            # Fetch enhanced transaction data via Helius
            try:
                r = client.post(
                    f"https://api.helius.xyz/v0/transactions/?api-key={key}",
                    json={"transactions": signatures[:max_per_program]},
                    timeout=30,
                )
                r.raise_for_status()
                enhanced = r.json()
            except Exception as e:
                console.print(f"    [dim]Skip enhanced: {e}[/dim]")
                time.sleep(DELAY)
                continue

            for tx in enhanced:
                tx_content = json.dumps(tx, indent=2)
                if len(tx_content) < 100:
                    continue

                sig = tx.get("signature", "unknown")[:16]
                record = Record(
                    id=Record.make_id(tx_content),
                    source=f"onchain/helius-tx/{program_id}",
                    source_type="code",
                    content=tx_content,
                    language="json",
                    license="Apache-2.0",
                    metadata={
                        "program_id": program_id,
                        "program_name": name,
                        "transaction_sig": tx.get("signature", ""),
                        "tx_type": tx.get("type", "unknown"),
                        "collected_at": today_str(),
                    },
                )
                records.append(record)

            console.print(f"    [green]✓ {len(enhanced)} transactions[/green]")
            time.sleep(DELAY)

    if records:
        out_path = PROCESSED_DIR / "onchain-transactions.jsonl"
        count = write_jsonl(records, out_path)
        console.print(f"\n[bold green]✓ {count} transaction records → {out_path.name}[/bold green]")
    else:
        console.print("\n[yellow]No transaction records extracted[/yellow]")


if __name__ == "__main__":
    app()
