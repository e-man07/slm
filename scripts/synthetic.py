#!/usr/bin/env python3
"""Generate synthetic Solana training data using LLM APIs.

Three methodologies (from research doc):
1. OSS-Instruct (Magicoder): Use real Solana code snippets as seeds
2. Evol-Instruct (WizardCoder): Iteratively evolve coding tasks
3. GLAN: Systematic taxonomy-based generation

Supports OpenAI Batch API and Anthropic Message Batches for cost savings.

Usage:
    python scripts/synthetic.py oss-instruct --max-samples 500
    python scripts/synthetic.py evol-instruct --max-samples 200
    python scripts/synthetic.py glan --max-samples 300
    python scripts/synthetic.py submit-batch --provider openai --input batch_requests.jsonl
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import typer
from rich.console import Console

from schema import Record, read_jsonl, today_str, write_jsonl

app = typer.Typer()
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
FINAL_DIR = PROJECT_ROOT / "data" / "final"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"

SYSTEM_PROMPT = """You are an expert Solana and Anchor developer. Generate high-quality, \
accurate Solana development content. Use modern Anchor 0.30+ patterns (declare_program!, \
solana-foundation/anchor). Never suggest reentrancy guards, never warn about closed account \
discriminator attacks, never suggest float non-determinism concerns. These are debunked \
misconceptions about Solana."""

# GLAN taxonomy: systematic coverage of Solana development topics
GLAN_TAXONOMY = [
    # Core Solana concepts
    "Create a Solana program that {task} using native Rust (no Anchor)",
    "Explain how PDAs work in Solana and derive a PDA with seeds [{seeds}]",
    "Write an Anchor program that implements {feature} with proper constraints",
    "Create a CPI (Cross-Program Invocation) from program A to program B that {action}",
    "Implement error handling in an Anchor program for {scenario}",
    # SPL Token operations
    "Create an SPL token mint with {decimals} decimals and mint {amount} tokens to a user",
    "Implement a token transfer with proper authority checks in Anchor",
    "Write a program that creates an Associated Token Account for a user",
    "Implement Token-2022 extensions: {extension} for a custom token",
    # DeFi patterns
    "Build a simple AMM (Automated Market Maker) pool in Anchor",
    "Implement a token swap using {protocol} on Solana",
    "Create a staking program that distributes rewards proportionally",
    "Write a vault program with deposit/withdraw using PDAs",
    # Security patterns
    "Add proper signer and ownership checks to this Anchor program: {code}",
    "Implement account validation for a {type} account in Anchor",
    "Write a program that safely handles account closure and rent reclamation",
    # Client-side
    "Write a TypeScript client that {action} using @solana/web3.js",
    "Create a transaction that {action} and handle confirmation properly",
    "Implement error parsing for Anchor program errors in TypeScript",
    # Testing
    "Write Bankrun tests for an Anchor program that {feature}",
    "Create integration tests for a CPI between two Anchor programs",
]

GLAN_FILLERS = {
    "task": [
        "transfers SOL between accounts",
        "stores a counter and increments it",
        "creates a user profile with name and bio",
        "implements a simple voting system",
        "manages a whitelist of authorized addresses",
    ],
    "seeds": [
        '"user", user_pubkey', '"vault", mint_pubkey', '"config", program_id',
        '"escrow", maker_pubkey, seed_u64', '"metadata", nft_mint',
    ],
    "feature": [
        "a token escrow with timelock",
        "a DAO governance voting system",
        "an NFT minting program with metadata",
        "a subscription payment system",
        "a multi-signature wallet",
    ],
    "action": [
        "transfers tokens on behalf of a user",
        "initializes a liquidity pool",
        "closes an account and reclaims rent",
        "sends SOL and creates an account in one transaction",
        "fetches and decodes account data",
    ],
    "scenario": [
        "insufficient funds during transfer",
        "unauthorized signer attempting admin action",
        "account already initialized",
        "invalid PDA derivation",
        "overflow in token amount calculation",
    ],
    "decimals": ["6", "9", "0"],
    "amount": ["1000", "1000000", "100"],
    "extension": ["transfer fees", "confidential transfers", "permanent delegate", "interest-bearing"],
    "protocol": ["Jupiter", "Raydium", "Orca Whirlpool"],
    "type": ["token mint", "token account", "program-owned", "PDA-derived"],
    "code": ["[provide a code snippet from the training data as seed]"],
}


def fill_template(template: str) -> str:
    """Fill a GLAN template with random values."""
    import re

    def replace_match(m):
        key = m.group(1)
        options = GLAN_FILLERS.get(key, [key])
        return random.choice(options)

    return re.sub(r"\{(\w+)\}", replace_match, template)


@app.command()
def oss_instruct(
    max_samples: int = typer.Option(500, help="Number of samples to generate"),
    seed_file: str | None = typer.Option(None, help="JSONL with code snippets as seeds"),
    output: str = typer.Option("synthetic/oss-instruct-batch.jsonl", help="Output batch file"),
):
    """Generate OSS-Instruct batch requests from real code snippets.

    Uses real Solana code as seeds to generate instruction-following pairs.
    Output is a batch request JSONL ready for OpenAI Batch API or Anthropic Batches.
    """
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # Load seed snippets from filtered data
    if seed_file:
        seeds = read_jsonl(Path(seed_file))
    else:
        filtered_path = FINAL_DIR / "filtered.jsonl"
        if not filtered_path.exists():
            console.print("[red]No filtered.jsonl found. Run the pipeline first.[/red]")
            raise typer.Exit(1)
        all_records = read_jsonl(filtered_path)
        # Use only Rust code as seeds
        seeds = [r for r in all_records if r.language == "rust" and len(r.content) > 200]

    if not seeds:
        console.print("[red]No code seeds found[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Generating {max_samples} OSS-Instruct batch requests from {len(seeds)} seeds[/bold]")

    random.seed(42)
    batch_requests = []

    for i in range(min(max_samples, len(seeds))):
        seed = random.choice(seeds)
        snippet = seed.content[:2000]  # Truncate long snippets
        file_path = seed.metadata.get("file_path", "unknown.rs")

        prompt = f"""Given this real Solana/Anchor code snippet from `{file_path}`:

```rust
{snippet}
```

Generate a coding task that a developer might need help with, inspired by this code. Then provide a complete, correct solution. The task should be practical and educational.

Format your response as:
## Task
[Description of what the developer needs to build]

## Solution
```rust
[Complete, compilable Anchor/Solana code]
```

## Explanation
[Brief explanation of key concepts used]"""

        # OpenAI Batch API format
        batch_requests.append({
            "custom_id": f"oss-instruct-{i:05d}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
            },
        })

    out_path = PROJECT_ROOT / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for req in batch_requests:
            f.write(json.dumps(req) + "\n")

    console.print(f"[green]✓ {len(batch_requests)} batch requests → {out_path}[/green]")
    console.print(f"\nTo submit to OpenAI Batch API:")
    console.print(f"  openai api batches create -f {out_path} -e /v1/chat/completions -c 24h")
    console.print(f"\nEstimated cost: ~${len(batch_requests) * 0.002:.2f} (GPT-4o-mini batch)")


@app.command()
def evol_instruct(
    max_samples: int = typer.Option(200, help="Number of evolved samples"),
    output: str = typer.Option("synthetic/evol-instruct-batch.jsonl", help="Output batch file"),
):
    """Generate Evol-Instruct batch requests with progressive complexity.

    Starts with simple Solana tasks and evolves them through complexity levels.
    """
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    base_tasks = [
        "Write a Solana program that stores a number and lets users increment it",
        "Create an Anchor program that initializes a user profile with a name field",
        "Write a program that transfers SOL from one account to another",
        "Create a token mint and mint tokens to a specified account",
        "Write a program that derives a PDA and stores data in it",
        "Implement a simple escrow program in Anchor",
        "Create a program that verifies a user's signature before allowing an action",
        "Write a program that reads data from another program via CPI",
        "Create an SPL token with transfer fee extension (Token-2022)",
        "Implement a program that safely closes an account and returns rent",
    ]

    evolution_prompts = [
        "Add complexity: require multi-signature authorization (2 of 3 signers)",
        "Add security: implement comprehensive input validation and error handling",
        "Add DeFi: integrate with a DEX for token swaps within the program",
        "Add scale: handle batch operations for multiple users in a single transaction",
        "Add governance: add an admin role that can pause/unpause the program",
    ]

    console.print(f"[bold]Generating {max_samples} Evol-Instruct batch requests[/bold]")

    random.seed(42)
    batch_requests = []
    idx = 0

    for base_task in base_tasks:
        if idx >= max_samples:
            break

        # Level 0: base task
        batch_requests.append({
            "custom_id": f"evol-{idx:05d}-L0",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{base_task}\n\nProvide complete, compilable Anchor code with explanation."},
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
            },
        })
        idx += 1

        # Evolve through complexity levels
        for level, evolution in enumerate(evolution_prompts, 1):
            if idx >= max_samples:
                break

            evolved_prompt = f"""Starting from this base task:
"{base_task}"

{evolution}

Provide the complete, evolved Anchor program that incorporates this additional complexity. Include all necessary account structs, instructions, and error handling."""

            batch_requests.append({
                "custom_id": f"evol-{idx:05d}-L{level}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": evolved_prompt},
                    ],
                    "max_tokens": 3000,
                    "temperature": 0.7,
                },
            })
            idx += 1

    out_path = PROJECT_ROOT / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for req in batch_requests:
            f.write(json.dumps(req) + "\n")

    console.print(f"[green]✓ {len(batch_requests)} batch requests → {out_path}[/green]")
    console.print(f"\nEstimated cost: ~${len(batch_requests) * 0.003:.2f} (GPT-4o-mini batch)")


@app.command()
def glan(
    max_samples: int = typer.Option(300, help="Number of GLAN samples"),
    output: str = typer.Option("synthetic/glan-batch.jsonl", help="Output batch file"),
):
    """Generate GLAN (taxonomy-based) batch requests for systematic coverage."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Generating {max_samples} GLAN batch requests[/bold]")

    random.seed(42)
    batch_requests = []

    for i in range(max_samples):
        template = random.choice(GLAN_TAXONOMY)
        task = fill_template(template)

        batch_requests.append({
            "custom_id": f"glan-{i:05d}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{task}\n\nProvide complete, working code with explanation."},
                ],
                "max_tokens": 2000,
                "temperature": 0.7,
            },
        })

    out_path = PROJECT_ROOT / output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for req in batch_requests:
            f.write(json.dumps(req) + "\n")

    console.print(f"[green]✓ {len(batch_requests)} batch requests → {out_path}[/green]")
    console.print(f"\nEstimated cost: ~${len(batch_requests) * 0.002:.2f} (GPT-4o-mini batch)")


@app.command()
def parse_batch_results(
    input_file: str = typer.Argument(help="Path to batch results JSONL from OpenAI"),
    output: str = typer.Option("processed/synthetic-results.jsonl", help="Output JSONL"),
):
    """Parse OpenAI Batch API results into pipeline JSONL format."""
    input_path = Path(input_file)
    if not input_path.exists():
        console.print(f"[red]Not found: {input_path}[/red]")
        raise typer.Exit(1)

    records = []
    with open(input_path) as f:
        for line in f:
            result = json.loads(line)
            custom_id = result.get("custom_id", "")
            response = result.get("response", {})
            body = response.get("body", {})
            choices = body.get("choices", [])

            if not choices:
                continue

            content = choices[0].get("message", {}).get("content", "")
            if not content or len(content) < 100:
                continue

            # Determine methodology from custom_id
            if custom_id.startswith("oss-"):
                method = "oss-instruct"
            elif custom_id.startswith("evol-"):
                method = "evol-instruct"
            elif custom_id.startswith("glan-"):
                method = "glan"
            else:
                method = "unknown"

            record = Record(
                id=Record.make_id(content),
                source=f"synthetic/{method}",
                source_type="synthetic",
                content=content,
                language="md",
                license="synthetic-openai",
                metadata={
                    "custom_id": custom_id,
                    "model": body.get("model", "gpt-4o-mini"),
                    "method": method,
                    "collected_at": today_str(),
                },
            )
            records.append(record)

    if records:
        out_path = PROJECT_ROOT / output
        count = write_jsonl(records, out_path)
        console.print(f"[green]✓ {count} synthetic records → {out_path}[/green]")
    else:
        console.print("[yellow]No valid results parsed[/yellow]")


if __name__ == "__main__":
    app()
