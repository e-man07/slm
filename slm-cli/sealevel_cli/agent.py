"""Agent loop orchestrator for Sealevel CLI.

Manages the LLM ↔ tool execution cycle: stream response, parse tool calls,
execute tools locally, send results back, repeat until done.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from sealevel_cli.client import SealevelError
from sealevel_cli.display import (
    console,
    print_assistant_label,
    print_error,
    print_info,
    print_response_separator,
    print_repl_timing,
    print_warning,
    stream_with_spinner,
)
from sealevel_cli.permissions import PermissionPolicy, check_permission
from sealevel_cli.tool_parser import ToolCall, parse as parse_tool_calls
from sealevel_cli.tools import TOOL_DEFINITIONS, ToolResult, execute as execute_tool

if TYPE_CHECKING:
    from sealevel_cli.session import Session


# ── Agent system prompt extension ──

AGENT_TOOL_PROMPT = """
You have access to tools for reading, writing, and searching files, and running commands.

When you need to use a tool, output a tool call in this exact format:
<tool_call>{"name": "tool_name", "arguments": {"param": "value"}}</tool_call>

Available tools:
"""

# Build tool list dynamically from definitions
for _td in TOOL_DEFINITIONS:
    _params = _td["parameters"]["properties"]
    _required = _td["parameters"].get("required", [])
    _args_desc = ", ".join(
        f"{k} ({'required' if k in _required else 'optional'})"
        for k in _params
    )
    AGENT_TOOL_PROMPT += f"- {_td['name']}: {_td['description']}. Args: {_args_desc}\n"

AGENT_TOOL_PROMPT += """
Example:
User: What's in src/lib.rs?
Assistant: I'll read the file.
<tool_call>{"name": "read_file", "arguments": {"path": "src/lib.rs"}}</tool_call>

Rules:
- Use tools when you need to read, write, or search files, or run commands
- You may use multiple tool calls in sequence across turns
- After receiving tool results, continue working or respond to the user
- When done, respond normally without <tool_call> tags
"""


def format_tool_results(calls: list[ToolCall], results: list[ToolResult]) -> str:
    """Format tool results as a user message for the next LLM turn."""
    parts = []
    for tc, result in zip(calls, results):
        status = "success" if result.success else "error"
        parts.append(
            f'<tool_result name="{tc.name}" status="{status}">\n'
            f"{result.output}\n"
            f"</tool_result>"
        )
    return "\n\n".join(parts)


def prompt_permission(tool_name: str, args: dict) -> str:
    """Prompt user for permission to execute a tool. Returns 'y', 'n', or 'a'."""
    from rich.text import Text

    # Build description
    if tool_name in ("write_file", "edit_file"):
        desc = f"{tool_name}: {args.get('path', '?')}"
    elif tool_name == "run_command":
        desc = f"run: {args.get('command', '?')}"
    else:
        desc = tool_name

    msg = Text()
    msg.append("▸ ", style="accent")
    msg.append(f"Allow {desc}? ", style="muted")
    msg.append("[y/N/a] ", style="accent.dim")
    console.print(msg, end="")

    try:
        response = input().strip().lower()
        return response if response in ("y", "n", "a") else "n"
    except (KeyboardInterrupt, EOFError):
        console.print()
        return "n"


def _print_tool_call(tc: ToolCall, needs_approval: bool) -> None:
    """Display a tool call panel."""
    from rich.panel import Panel
    from rich.text import Text

    # Build content
    lines = []
    for k, v in tc.args.items():
        val_str = str(v)
        if len(val_str) > 60:
            val_str = val_str[:57] + "..."
        lines.append(f"  {k}: {val_str}")
    content = "\n".join(lines) if lines else "  (no arguments)"

    suffix = " (requires approval)" if needs_approval else ""
    title = Text(f" {tc.name}{suffix} ", style="label")

    panel = Panel(
        content,
        title=title,
        border_style="border",
        padding=(0, 1),
        width=min(console.width, 60),
    )
    console.print(panel)


def _print_tool_result(tc: ToolCall, result: ToolResult) -> None:
    """Display tool execution result."""
    from rich.text import Text

    msg = Text()
    if result.success:
        msg.append("✓ ", style="ok")
        msg.append(tc.name.upper(), style="label")
        # Show summary
        summary = result.output.split("\n")[0][:60]
        msg.append(f"  {summary}", style="muted")
    else:
        msg.append("✗ ", style="err")
        msg.append(tc.name.upper(), style="label")
        msg.append(f"  {result.output[:60]}", style="muted")
    console.print(msg)


class AgentLoop:
    """Orchestrates the LLM ↔ tool execution loop."""

    MAX_ITERATIONS = 15

    def __init__(
        self,
        cwd: Path | None = None,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self.cwd = cwd or Path.cwd()
        self.policy = policy or PermissionPolicy()

    def run(self, user_message: str, session: "Session") -> None:
        """Run the agent loop until completion or max iterations."""
        # Local history for the agent loop (not persisted to session until done)
        local_history = list(session.history)
        local_history.append({"role": "user", "content": user_message})

        final_response = ""
        prose = ""
        t0 = time.monotonic()

        try:
            for iteration in range(self.MAX_ITERATIONS):
                if iteration == self.MAX_ITERATIONS - 2:
                    print_warning(f"Agent approaching iteration limit ({self.MAX_ITERATIONS})")

                # Stream LLM response
                console.print()
                full_text = stream_with_spinner(
                    session.client.stream_chat(
                        local_history[-1]["content"],
                        history=local_history[:-1],
                    ),
                    label=(iteration == 0),  # Only show SEALEVEL label on first iteration
                )

                # Parse for tool calls
                tool_calls, prose = parse_tool_calls(full_text)

                # No tool calls → this is the final response
                if not tool_calls:
                    final_response = full_text
                    break

                # Append assistant response with tool calls to local history
                local_history.append({"role": "assistant", "content": full_text})

                # Execute each tool call
                results: list[ToolResult] = []
                for tc in tool_calls:
                    perm = check_permission(tc.name, tc.args, self.policy)

                    _print_tool_call(tc, needs_approval=(perm is None))

                    if perm is False:
                        result = ToolResult(False, "Permission denied: sensitive file or dangerous command")
                        _print_tool_result(tc, result)
                        results.append(result)
                        continue

                    if perm is None:
                        answer = prompt_permission(tc.name, tc.args)
                        if answer == "n":
                            result = ToolResult(False, "Permission denied by user")
                            _print_tool_result(tc, result)
                            results.append(result)
                            continue
                        if answer == "a":
                            # Approve all of this permission level
                            from sealevel_cli.permissions import PERMISSION_MAP
                            level = PERMISSION_MAP.get(tc.name, "execute")
                            if level == "write":
                                self.policy.auto_writes = True
                            elif level == "execute":
                                self.policy.auto_commands = True

                    # Execute the tool
                    try:
                        result = execute_tool(tc.name, tc.args, cwd=self.cwd)
                    except Exception as e:
                        result = ToolResult(False, f"Tool execution error: {e}")
                    _print_tool_result(tc, result)
                    results.append(result)

                # Send tool results back as user message
                result_message = format_tool_results(tool_calls, results)
                local_history.append({"role": "user", "content": result_message})

            else:
                # Max iterations reached
                print_warning("Agent reached iteration limit. Stopping.")
                final_response = prose or "Agent stopped at iteration limit."

        except KeyboardInterrupt:
            console.print("\n[muted](agent cancelled)[/muted]")
            # Preserve what was accomplished
            if final_response or prose:
                session.history.append({"role": "user", "content": user_message})
                session.history.append({"role": "assistant", "content": final_response or prose or "(cancelled)"})
                session.turns += 1
            return
        except SealevelError as e:
            print_error(str(e))
            # Preserve what was accomplished before the error
            if final_response or prose:
                session.history.append({"role": "user", "content": user_message})
                session.history.append({"role": "assistant", "content": final_response or prose})
                session.turns += 1
            return

        # Persist to session: original user message + final response
        elapsed = time.monotonic() - t0
        session.history.append({"role": "user", "content": user_message})
        session.history.append({"role": "assistant", "content": final_response})
        session.turns += 1
        tokens = session._capture_tokens()
        print_repl_timing(elapsed, tokens)
        print_response_separator()
