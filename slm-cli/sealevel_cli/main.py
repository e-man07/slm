"""Sealevel CLI — command line interface for Sealevel.

Usage:
    slm                      - Start interactive session
    slm -p "prompt"          - One-shot mode (pipe-friendly)
    slm config --show        - Manage configuration
"""
from __future__ import annotations

import os
import sys
from typing import Annotated, Optional

import typer

from sealevel_cli import __version__
from sealevel_cli.client import SealevelClient, SealevelError, clean_model_response, fix_anchor_code
from sealevel_cli.config import get_value, load_config, set_value
from sealevel_cli.display import (
    console,
    print_config_set,
    print_config_table,
    print_error,
    print_header,
    print_info,
    print_version,
    print_warning,
    stream_with_spinner,
)


def _version_callback(value: bool) -> None:
    if value:
        print_version()
        raise typer.Exit()


app = typer.Typer(
    name="slm",
    help="Sealevel CLI — Solana/Anchor development assistant. Run 'slm' to start.",
    no_args_is_help=False,
    invoke_without_command=True,
    add_completion=True,
)


def _get_config_dir() -> str | None:
    return os.environ.get("SEALEVEL_CONFIG_DIR")


def _make_client(quiet: bool = False) -> SealevelClient:
    config_dir = _get_config_dir()
    api_key = get_value("api_key", config_dir=config_dir)
    api_url = get_value("api_url", config_dir=config_dir) or "https://www.sealevel.tech"
    if not api_key and not quiet:
        print_warning(
            "No API key configured.\n"
            "  Get one at https://sealevel.tech/dashboard\n"
            "  Then run: slm config --api-key slm_xxxx"
        )
        console.print()
    return SealevelClient(base_url=api_url, api_key=api_key)


@app.callback()
def _root(
    ctx: typer.Context,
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=_version_callback, is_eager=True, help="Show version and exit."),
    ] = None,
    prompt: Annotated[
        Optional[str],
        typer.Option("--prompt", "-p", help="One-shot mode: send prompt and exit (pipe-friendly)."),
    ] = None,
    continue_session: Annotated[
        bool,
        typer.Option("--continue", "-c", help="Continue the most recent session."),
    ] = False,
) -> None:
    """Sealevel CLI — Solana/Anchor development assistant."""
    _ = version
    if ctx.invoked_subcommand is not None:
        return

    if continue_session:
        client = _make_client()
        from sealevel_cli.session import Session
        try:
            sessions = client.list_sessions()
            if not sessions:
                print_info("No previous sessions found.")
                raise typer.Exit()
            Session.from_server(client, sessions[0]["id"]).run()
        except SealevelError as e:
            print_error(str(e))
            raise typer.Exit(code=1)
        except SystemExit:
            pass
        return

    if prompt is not None:
        # One-shot pipe mode
        client = _make_client(quiet=True)

        # Read stdin if piped
        stdin_text = ""
        if not sys.stdin.isatty():
            stdin_text = sys.stdin.read().strip()

        full_prompt = f"{stdin_text}\n\n{prompt}".strip() if stdin_text else prompt

        try:
            full = stream_with_spinner(
                client.stream_chat(full_prompt),
                label=False,
                render_md=False,
            )
            full = fix_anchor_code(clean_model_response(full))
        except SealevelError as e:
            print_error(str(e))
            raise typer.Exit(code=1)
        return

    # Interactive session (default)
    client = _make_client()
    from sealevel_cli.session import Session
    try:
        Session(client).run()
    except SystemExit:
        pass


@app.command()
def config(
    api_key: Annotated[Optional[str], typer.Option("--api-key", help="Set API key")] = None,
    show: Annotated[bool, typer.Option("--show", help="Show config")] = False,
    api_url: Annotated[Optional[str], typer.Option("--api-url", help="Set API URL")] = None,
    mode: Annotated[Optional[str], typer.Option("--mode", help="Set mode: 'quality' or 'fast'")] = None,
) -> None:
    """Manage Sealevel CLI configuration."""
    config_dir = _get_config_dir()
    if show:
        print_header("CONFIG")
        cfg = load_config(config_dir=config_dir)
        print_config_table(cfg)
        return
    if not api_key and not api_url and not mode:
        print_info("Use --show to view config, or set values with --api-key, --api-url, --mode")
        return
    if api_key:
        if not api_key.startswith("slm_") or len(api_key) < 16:
            print_error("Invalid API key format. Keys must start with 'slm_' and be at least 16 characters.")
            raise typer.Exit(code=1)
        set_value("api_key", api_key, config_dir=config_dir)
        print_config_set("api_key", api_key)
    if api_url:
        set_value("api_url", api_url, config_dir=config_dir)
        print_config_set("api_url", api_url)
    if mode:
        if mode not in ("quality", "fast"):
            print_error("Mode must be 'quality' or 'fast'")
            raise typer.Exit(code=1)
        set_value("mode", mode, config_dir=config_dir)
        print_config_set("mode", mode)


if __name__ == "__main__":
    app()
