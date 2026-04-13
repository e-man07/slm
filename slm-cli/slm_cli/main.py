"""SLM CLI - Command line interface for the Solana Language Model.

Commands:
    slm chat "prompt"        - One-shot chat with streaming output
    slm chat                 - Interactive REPL mode
    slm explain --tx <sig>   - Explain a transaction
    slm explain --error <code> - Decode an error code
    slm config --api-key <key> - Save API key
    slm config --show        - Show current config
"""
from __future__ import annotations

import os
import sys
from typing import Annotated, Optional

import typer
from rich.console import Console

from slm_cli.client import SLMClient
from slm_cli.config import get_value, load_config, set_value
from slm_cli.display import (
    console,
    create_spinner,
    print_done,
    print_error_result,
    print_markdown,
    print_streaming,
)

app = typer.Typer(
    name="slm",
    help="SLM - Solana Language Model CLI. Chat, explain transactions, decode errors.",
    no_args_is_help=True,
)


def _get_config_dir() -> str | None:
    return os.environ.get("SLM_CONFIG_DIR")


def _make_client() -> SLMClient:
    """Create an SLMClient from stored config."""
    config_dir = _get_config_dir()
    api_key = get_value("api_key", config_dir=config_dir)
    api_url = get_value("api_url", config_dir=config_dir) or "https://slm.dev/api"
    return SLMClient(base_url=api_url, api_key=api_key)


@app.command()
def chat(
    prompt: Annotated[
        Optional[str],
        typer.Argument(help="Chat message (omit for interactive REPL)"),
    ] = None,
) -> None:
    """Chat with SLM. Pass a prompt for one-shot, or omit for interactive REPL."""
    client = _make_client()

    if prompt:
        # One-shot mode
        try:
            for chunk in client.stream_chat(prompt):
                print_streaming(chunk)
            print_done()
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(code=1)
    else:
        # Interactive REPL mode
        console.print("[bold]SLM Interactive Chat[/bold] (type 'exit' or Ctrl+C to quit)\n")
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
def config(
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", help="Set your SLM API key"),
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
    """Manage SLM CLI configuration."""
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
