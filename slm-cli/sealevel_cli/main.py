"""Sealevel CLI — command line interface for Sealevel.

Usage:
    slm                      - Start interactive session
    slm login                - Authenticate via browser (OAuth device flow)
    slm logout               - Clear stored credentials
    slm -p "prompt"          - One-shot mode (pipe-friendly)
    slm config --show        - Manage configuration
"""
from __future__ import annotations

import os
import sys
import time
import webbrowser
from typing import Annotated, Optional

import typer

from sealevel_cli import __version__
from sealevel_cli.client import SealevelClient, SealevelError, clean_model_response, fix_anchor_code
from sealevel_cli.config import clear_value, get_value, load_config, set_value

from prompt_toolkit import prompt as pt_prompt
from sealevel_cli.display import (
    console,
    print_config_set,
    print_config_table,
    print_error,
    print_header,
    print_info,
    print_success,
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


def _first_run_setup(config_dir: str | None) -> str | None:
    """Interactive first-run onboarding. Returns API key or None."""
    print_header("WELCOME")
    console.print()
    print_info("Sign in to get started:")
    console.print()
    print_info("  1. Browser login (recommended)")
    print_info("  2. Paste API key manually")
    console.print()
    try:
        choice = pt_prompt("Choose [1/2]: ").strip()
        if choice == "1":
            try:
                _device_login_flow()
                return get_value("api_key", config_dir=config_dir)
            except (SystemExit, Exception):
                return None
        elif choice == "2":
            print_info("Get your key at https://sealevel.tech/dashboard")
            key = pt_prompt("Paste your API key: ", is_password=True).strip()
            if not key:
                return None
            if not key.startswith("slm_") or len(key) < 16:
                print_error("Invalid key format. Must start with 'slm_' and be 16+ chars.")
                return None
            set_value("api_key", key, config_dir=config_dir)
            print_success("API key saved!")
            console.print()
            return key
        else:
            return None
    except (KeyboardInterrupt, EOFError):
        console.print()
        return None


def _make_client(quiet: bool = False) -> SealevelClient:
    config_dir = _get_config_dir()
    api_key = get_value("api_key", config_dir=config_dir)
    api_url = get_value("api_url", config_dir=config_dir) or "https://www.sealevel.tech"
    mode = get_value("mode", config_dir=config_dir) or "quality"
    if not api_key and not quiet:
        if sys.stdin.isatty():
            api_key = _first_run_setup(config_dir)
        if not api_key:
            print_warning(
                "No API key configured.\n"
                "  Run: slm login  (recommended)\n"
                "  Or:  slm config --api-key slm_xxxx"
            )
            console.print()
    return SealevelClient(base_url=api_url, api_key=api_key, mode=mode)


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
        keyring_key = get_value("api_key", config_dir=config_dir)
        if keyring_key:
            cfg["api_key"] = keyring_key
        print_config_table(cfg)
        return
    if api_key is None and api_url is None and not mode:
        print_info("Use --show to view config, or set values with --api-key, --api-url, --mode")
        return
    if api_key is not None:
        if not api_key.startswith("slm_") or len(api_key) < 16:
            print_error("Invalid API key format. Keys must start with 'slm_' and be at least 16 characters.")
            raise typer.Exit(code=1)
        set_value("api_key", api_key, config_dir=config_dir)
        print_config_set("api_key", api_key)
    if api_url is not None:
        if not api_url.startswith(("http://", "https://")):
            print_error("Invalid URL. Must start with http:// or https://")
            raise typer.Exit(code=1)
        set_value("api_url", api_url, config_dir=config_dir)
        print_config_set("api_url", api_url)
    if mode:
        if mode not in ("quality", "fast"):
            print_error("Mode must be 'quality' or 'fast'")
            raise typer.Exit(code=1)
        set_value("mode", mode, config_dir=config_dir)
        print_config_set("mode", mode)


def _device_login_flow() -> None:
    """Execute OAuth device auth flow: get code, open browser, poll for completion."""
    config_dir = _get_config_dir()
    api_url = get_value("api_url", config_dir=config_dir) or "https://www.sealevel.tech"
    client = SealevelClient(base_url=api_url)

    try:
        data = client.initiate_device_auth()
    except SealevelError as e:
        print_error(str(e))
        raise typer.Exit(code=1)

    code = data["userCode"]
    url = data["verificationUrl"]
    interval = data.get("interval", 5)
    expires_in = data.get("expiresIn", 600)

    # Display code and open browser
    console.print()
    print_header("LOGIN")
    console.print()
    from rich.panel import Panel
    from rich.text import Text
    code_text = Text(code, style="bold", justify="center")
    code_text.stylize("accent")
    panel = Panel(
        code_text,
        title=Text(" DEVICE CODE ", style="label"),
        border_style="border",
        padding=(1, 4),
        width=30,
    )
    console.print(panel)
    console.print()
    print_info(f"Opening {url}")
    print_info("Enter the code above to authorize this CLI.")
    console.print()

    try:
        webbrowser.open(f"{url}?code={code}")
    except Exception:
        print_info(f"Open manually: {url}?code={code}")

    # Poll for completion
    from sealevel_cli.display import create_spinner
    deadline = time.monotonic() + expires_in

    spinner = create_spinner("Waiting for browser authorization...")
    try:
        spinner.start()
        while time.monotonic() < deadline:
            time.sleep(interval)
            try:
                result = client.poll_device_auth(code)
            except SealevelError:
                continue

            if result.get("status") == "complete":
                spinner.stop()
                api_key = result["apiKey"]
                user = result.get("user", {})
                set_value("api_key", api_key, config_dir=config_dir)
                console.print()
                print_success(f"Logged in as {user.get('name', 'user')} ({user.get('tier', 'free')} tier)")
                print_config_set("api_key", api_key)
                return
    except KeyboardInterrupt:
        spinner.stop()
        console.print("\n")
        print_info("Login cancelled.")
        raise typer.Exit()
    finally:
        try:
            spinner.stop()
        except Exception:
            pass

    print_error("Login timed out. Run 'slm login' to try again.")
    raise typer.Exit(code=1)


@app.command()
def login() -> None:
    """Authenticate via browser (OAuth device flow)."""
    config_dir = _get_config_dir()
    existing = get_value("api_key", config_dir=config_dir)
    if existing:
        print_info(f"Already logged in (key: {existing[:8]}···{existing[-4:]})")
        print_info("Run 'slm logout' first, or 'slm login' will overwrite.")
    _device_login_flow()


@app.command()
def logout() -> None:
    """Clear stored API key and credentials."""
    config_dir = _get_config_dir()
    api_key = get_value("api_key", config_dir=config_dir)
    if not api_key:
        print_info("Not logged in.")
        return
    clear_value("api_key", config_dir=config_dir)
    print_success("Logged out. API key cleared.")


if __name__ == "__main__":
    app()
