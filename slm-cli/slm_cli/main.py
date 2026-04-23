"""Sealevel CLI - Command line interface for the Solana Language Model.

Commands:
    slm chat "prompt"        - One-shot chat with streaming output
    slm chat                 - Interactive REPL mode
    slm explain --tx <sig>   - Explain a transaction
    slm explain --error <code> - Decode an error code
    slm config --api-key <key> - Save API key
    slm config --show        - Show current config
"""
from __future__ import annotations

import json as _json
import os
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console

from slm_cli import __version__
from slm_cli.client import SLMClient, clean_model_response, fix_anchor_code
from slm_cli.config import get_value, load_config, set_value
from slm_cli.display import (
    console,
    create_spinner,
    print_done,
    print_error_result,
    print_markdown,
    print_streaming,
)


def _validate_file_path(file_path: str) -> str:
    """Resolve and validate a file path. Reject path traversal and sensitive files."""
    resolved = os.path.realpath(file_path)
    if not os.path.isfile(resolved):
        console.print(f"[red]File not found: {file_path}[/red]")
        raise typer.Exit(code=1)
    if os.path.getsize(resolved) > 1_000_000:
        console.print(f"[red]File too large (max 1MB): {file_path}[/red]")
        raise typer.Exit(code=1)
    basename = os.path.basename(resolved).lower()
    if basename in {'.env', '.env.local', 'credentials.json', 'id_rsa', 'id_ed25519', '.netrc'}:
        console.print(f"[red]Cannot read sensitive file: {basename}[/red]")
        raise typer.Exit(code=1)
    return resolved


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"slm-cli {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="slm",
    help="Sealevel — Solana Language Model CLI. Chat, generate, review, migrate, decode.",
    no_args_is_help=True,
    add_completion=True,
)


@app.callback()
def _root(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-v", callback=_version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = None,
) -> None:
    """Sealevel CLI — pass --help for commands."""
    _ = version  # consumed by callback


def _get_config_dir() -> str | None:
    return os.environ.get("SLM_CONFIG_DIR")


def _make_client() -> SLMClient:
    """Create an SLMClient from stored config."""
    config_dir = _get_config_dir()
    api_key = get_value("api_key", config_dir=config_dir)
    api_url = get_value("api_url", config_dir=config_dir) or "https://api.sealevel.tech"
    return SLMClient(base_url=api_url, api_key=api_key)


@app.command()
def chat(
    prompt: Annotated[
        Optional[str],
        typer.Argument(help="Chat message (omit for interactive REPL)"),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON to stdout (for scripting/piping to jq)."),
    ] = False,
) -> None:
    """Chat with Sealevel. Pass a prompt for one-shot, or omit for interactive REPL."""
    client = _make_client()

    if prompt:
        # One-shot mode
        try:
            if json_output:
                chunks: list[str] = []
                for chunk in client.stream_chat(prompt):
                    chunks.append(chunk)
                content = fix_anchor_code(clean_model_response("".join(chunks)))
                sys.stdout.write(_json.dumps({"prompt": prompt, "content": content}) + "\n")
                sys.stdout.flush()
            else:
                for chunk in client.stream_chat(prompt):
                    print_streaming(chunk)
                print_done()
        except Exception as e:
            if json_output:
                sys.stdout.write(_json.dumps({"error": str(e)}) + "\n")
                sys.exit(1)
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)
    else:
        # Interactive REPL mode
        console.print("[bold]Sealevel Interactive Chat[/bold] (type 'exit' or Ctrl+C to quit)\n")
        history: list[dict[str, str]] = []
        while True:
            try:
                user_input = console.input("[bold green]> [/bold green]")
                if user_input.strip().lower() in ("exit", "quit", "/quit", "/exit"):
                    break
                if not user_input.strip():
                    continue

                history.append({"role": "user", "content": user_input})
                full_response = ""
                for chunk in client.stream_chat(user_input, history=history[:-1]):
                    print_streaming(chunk)
                    full_response += chunk
                print_done()
                full_response = fix_anchor_code(clean_model_response(full_response))
                history.append({"role": "assistant", "content": full_response})
                console.print()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye![/dim]")
                break


@app.command()
def explain(
    tx: Annotated[
        Optional[str],
        typer.Option("--tx", help="Transaction signature to explain"),
    ] = None,
    error: Annotated[
        Optional[str],
        typer.Option("--error", help="Error code to decode (decimal or hex)"),
    ] = None,
) -> None:
    """Explain a Solana transaction or decode an error code."""
    client = _make_client()

    if not tx and not error:
        console.print("[red]Provide --tx <signature> or --error <code>[/red]")
        raise typer.Exit(code=1)

    if tx:
        try:
            console.print(f"[dim]Explaining transaction {tx[:16]}...[/dim]\n")
            for chunk in client.explain_tx(tx):
                print_streaming(chunk)
            print_done()
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)

    if error:
        try:
            console.print(f"[dim]Decoding error {error}...[/dim]\n")
            for chunk in client.explain_error(error):
                print_streaming(chunk)
            print_done()
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)


@app.command()
def review(
    file: Annotated[str, typer.Argument(help="Path to Rust/Anchor file to review")],
) -> None:
    """Review a local Solana/Anchor file for security issues and deprecated patterns."""
    client = _make_client()

    validated = _validate_file_path(file)
    with open(validated, "r") as f:
        code = f.read()

    prompt = (
        f"Review this Solana/Anchor code for security issues, deprecated patterns, "
        f"and common mistakes. Be specific and actionable.\n\n```rust\n{code}\n```"
    )
    try:
        console.print(f"[dim]Reviewing {file}...[/dim]\n")
        for chunk in client.stream_chat(prompt):
            print_streaming(chunk)
        print_done()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def migrate(
    file: Annotated[str, typer.Argument(help="Path to Rust/Anchor file to migrate")],
    write: Annotated[
        bool,
        typer.Option("--write", "-w", help="Overwrite file with migrated code"),
    ] = False,
) -> None:
    """Migrate old Anchor code to modern Anchor 0.30+ patterns."""
    client = _make_client()

    validated = _validate_file_path(file)
    with open(validated, "r") as f:
        code = f.read()

    prompt = (
        "Migrate this Solana/Anchor code to modern Anchor 0.30+ patterns. "
        "Update: declare_id! -> declare_program!, coral-xyz/anchor -> solana-foundation/anchor, "
        "manual space calculation -> InitSpace derive, bumps.get() -> ctx.bumps.field_name. "
        "Output ONLY the migrated code in a single ```rust block, no explanation.\n\n"
        f"```rust\n{code}\n```"
    )
    try:
        console.print(f"[dim]Migrating {file}...[/dim]\n")
        full = ""
        for chunk in client.stream_chat(prompt):
            if not write:
                print_streaming(chunk)
            full += chunk
        print_done()

        full = fix_anchor_code(clean_model_response(full))

        if write:
            # Extract code from ```rust block
            import re
            match = re.search(r"```(?:rust)?\n(.*?)```", full, re.DOTALL)
            new_code = match.group(1) if match else full
            with open(file, "w") as f:
                f.write(new_code)
            console.print(f"[green]✓[/green] Wrote migrated code to {file}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def gen(
    description: Annotated[str, typer.Argument(help="Program description, e.g. 'counter with increment and reset'")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Write output to file instead of stdout"),
    ] = None,
) -> None:
    """Generate a new Anchor program from a description."""
    client = _make_client()

    if output:
        output_dir = os.path.dirname(os.path.realpath(output)) or "."
        if not os.path.isdir(output_dir):
            console.print(f"[red]Output directory does not exist: {output_dir}[/red]")
            raise typer.Exit(code=1)

    prompt = (
        f"Write a complete, production-ready Anchor program for: {description}. "
        "Use modern Anchor 0.30+ patterns. Include all necessary accounts, instructions, and account structs. "
        "Output ONLY the Rust code in a single ```rust block, no explanation."
    )
    try:
        console.print(f"[dim]Generating program: {description}[/dim]\n")
        full = ""
        for chunk in client.stream_chat(prompt):
            if not output:
                print_streaming(chunk)
            full += chunk
        print_done()

        full = fix_anchor_code(clean_model_response(full))

        if output:
            import re
            match = re.search(r"```(?:rust)?\n(.*?)```", full, re.DOTALL)
            code = match.group(1) if match else full
            with open(output, "w") as f:
                f.write(code)
            console.print(f"[green]✓[/green] Wrote program to {output}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def tests(
    file: Annotated[str, typer.Argument(help="Path to Anchor program to generate tests for")],
) -> None:
    """Generate TypeScript tests for an Anchor program."""
    client = _make_client()

    validated = _validate_file_path(file)
    with open(validated, "r") as f:
        code = f.read()

    prompt = (
        "Write comprehensive TypeScript tests using @coral-xyz/anchor and mocha for this Anchor program. "
        "Cover all instructions with happy path and error cases. Output ONLY the TypeScript code.\n\n"
        f"```rust\n{code}\n```"
    )
    try:
        console.print(f"[dim]Generating tests for {file}...[/dim]\n")
        for chunk in client.stream_chat(prompt):
            print_streaming(chunk)
        print_done()
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def config(
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", help="Set your Sealevel API key"),
    ] = None,
    show: Annotated[
        bool,
        typer.Option("--show", help="Show current configuration"),
    ] = False,
    api_url: Annotated[
        Optional[str],
        typer.Option("--api-url", help="Set the API base URL"),
    ] = None,
    mode: Annotated[
        Optional[str],
        typer.Option("--mode", help="Set mode: 'quality' or 'fast'"),
    ] = None,
) -> None:
    """Manage Sealevel CLI configuration."""
    config_dir = _get_config_dir()

    if show:
        cfg = load_config(config_dir=config_dir)
        console.print("[bold]Current Configuration[/bold]\n")
        for key, value in sorted(cfg.items()):
            # Mask API key for display
            display_value = value
            if key == "api_key" and value and len(value) > 8:
                display_value = value[:8] + "..." + value[-4:]
            console.print(f"  {key}: {display_value}")
        return

    if not api_key and not api_url and not mode:
        console.print("[dim]Use --show to view config, or set values with --api-key, --api-url, --mode[/dim]")
        return

    if api_key:
        if not api_key.startswith("slm_") or len(api_key) < 16:
            console.print("[red]Invalid API key format. Keys must start with 'slm_' and be at least 16 characters.[/red]")
            raise typer.Exit(code=1)
        set_value("api_key", api_key, config_dir=config_dir)
        console.print(f"API key saved: {api_key[:8]}...{api_key[-4:]}")

    if api_url:
        set_value("api_url", api_url, config_dir=config_dir)
        console.print(f"API URL set: {api_url}")

    if mode:
        if mode not in ("quality", "fast"):
            console.print("[red]Mode must be 'quality' or 'fast'[/red]")
            raise typer.Exit(code=1)
        set_value("mode", mode, config_dir=config_dir)
        console.print(f"Mode set: {mode}")


if __name__ == "__main__":
    app()
