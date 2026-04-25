"""Permission model for agent tool execution.

Read-only tools (read_file, glob_files, grep_files) are auto-approved.
Mutation tools (write_file, edit_file) and execution (run_command) require user confirmation.
Sensitive files and dangerous commands are always denied regardless of policy.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from sealevel_cli.tools import SENSITIVE_FILES, SENSITIVE_EXTENSIONS


@dataclass
class PermissionPolicy:
    """Controls which tools are auto-approved."""
    auto_reads: bool = True
    auto_writes: bool = False
    auto_commands: bool = False


PERMISSION_MAP = {
    "read_file": "read",
    "glob_files": "read",
    "grep_files": "read",
    "write_file": "write",
    "edit_file": "write",
    "run_command": "execute",
}

# Commands that are always denied
DANGEROUS_COMMANDS = [
    re.compile(r"rm\s+-rf\s+/"),
    re.compile(r"rm\s+-rf\s+~"),
    re.compile(r"chmod\s+777"),
    re.compile(r"curl\s+.*\|\s*sh"),
    re.compile(r"wget\s+.*\|\s*sh"),
    re.compile(r"curl\s+.*\|\s*bash"),
    re.compile(r"wget\s+.*\|\s*bash"),
    re.compile(r"mkfs\."),
    re.compile(r"dd\s+if=.*/dev/"),
    re.compile(r":\(\)\s*\{"),  # Fork bomb
]


def _is_sensitive_path(path: str) -> bool:
    """Check if path refers to a sensitive file."""
    basename = os.path.basename(path).lower()
    if basename in SENSITIVE_FILES:
        return True
    _, ext = os.path.splitext(basename)
    if ext in SENSITIVE_EXTENSIONS:
        return True
    return False


def _is_dangerous_command(command: str) -> bool:
    """Check if a command matches dangerous patterns."""
    for pattern in DANGEROUS_COMMANDS:
        if pattern.search(command):
            return True
    return False


def check_permission(
    tool_name: str,
    args: dict,
    policy: PermissionPolicy,
) -> bool | None:
    """Check if a tool call is allowed.

    Returns:
        True  — auto-approved
        False — hard denied (sensitive file, dangerous command)
        None  — needs user prompt
    """
    # Security: always deny sensitive files
    path = args.get("path", "")
    if path and _is_sensitive_path(path):
        return False

    # Security: always deny dangerous commands
    if tool_name == "run_command":
        command = args.get("command", "")
        if _is_dangerous_command(command):
            return False

    level = PERMISSION_MAP.get(tool_name, "execute")

    if level == "read" and policy.auto_reads:
        return True
    if level == "write" and policy.auto_writes:
        return True
    if level == "execute" and policy.auto_commands:
        return True

    return None  # Needs user prompt
