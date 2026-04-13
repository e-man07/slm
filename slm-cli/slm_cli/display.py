"""Display formatting helpers using Rich.

Provides formatted output for error results, markdown, and spinners.
"""
from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

console = Console()


def format_error_result(
    program: str,
    name: str,
    code: int,
    hex_code: str,
    message: str,
) -> str:
    """Format an error lookup result as a readable string."""
    lines = [
        f"Program:  {program}",
        f"Error:    {name}",
        f"Code:     {code} ({hex_code})",
        f"Message:  {message}",
    ]
    return "\n".join(lines)


def print_error_result(
    program: str,
    name: str,
    code: int,
    hex_code: str,
    message: str,
) -> None:
    """Print a formatted error lookup result to the console."""
    text = format_error_result(program, name, code, hex_code, message)
    panel = Panel(text, title="Error Lookup", border_style="yellow")
    console.print(panel)


def format_markdown(text: str) -> str:
    """Convert markdown text to a string representation.

    For actual terminal rendering, use print_markdown instead.
    This returns the raw text for testing purposes.
    """
    # Strip common markdown syntax for plain-text representation
    result = text
    for char in ["#", "*", "_", "`"]:
        result = result.replace(char, "")
    return result.strip()


def print_markdown(text: str) -> None:
    """Render markdown to the terminal using Rich."""
    md = Markdown(text)
    console.print(md)


def create_spinner(message: str = "Thinking...") -> Status:
    """Create a Rich spinner/status indicator.

    Usage:
        with create_spinner("Loading..."):
            do_work()
    """
    return console.status(message, spinner="dots")


def print_streaming(chunk: str) -> None:
    """Print a streaming chunk without a newline."""
    console.print(chunk, end="", highlight=False)


def print_done() -> None:
    """Print a newline after streaming is complete."""
    console.print()
