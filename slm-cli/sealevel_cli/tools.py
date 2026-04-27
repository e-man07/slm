"""Tool definitions and executors for the Sealevel agent harness.

Provides 6 tools: read_file, write_file, edit_file, run_command, glob_files, grep_files.
Each tool has a JSON schema definition (for system prompt injection) and an executor function.
Security checks reuse patterns from commands.py (sensitive files, size limits).
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Max output size for tool results (64KB)
MAX_OUTPUT_SIZE = 65_536

# Max file size for reads (1MB)
MAX_FILE_SIZE = 1_000_000

# Default read limit (lines)
DEFAULT_READ_LIMIT = 200

# Default command timeout (seconds)
DEFAULT_CMD_TIMEOUT = 30

# Sensitive files that cannot be read or written
SENSITIVE_FILES = {
    ".env", ".env.local", ".env.production", ".env.staging",
    "credentials.json", "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa",
    ".netrc", ".npmrc",
}

SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx"}


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str


# ── Tool Definitions (injected into system prompt) ──

TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path (absolute or relative to project)"},
                "offset": {"type": "integer", "description": "Line to start from (0-based)"},
                "limit": {"type": "integer", "description": "Max lines to read"},
            },
            "required": ["path"],
        },
        "permission": "read",
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with content",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
        "permission": "write",
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file (search and replace)",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "old_text": {"type": "string", "description": "Exact text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
        "permission": "write",
    },
    {
        "name": "run_command",
        "description": "Execute a shell command and return output",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
            },
            "required": ["command"],
        },
        "permission": "execute",
    },
    {
        "name": "glob_files",
        "description": "Find files matching a glob pattern",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.rs')"},
                "path": {"type": "string", "description": "Directory to search in"},
            },
            "required": ["pattern"],
        },
        "permission": "read",
    },
    {
        "name": "grep_files",
        "description": "Search file contents with regex",
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "path": {"type": "string", "description": "Directory or file to search"},
                "glob": {"type": "string", "description": "File glob filter (e.g. '*.rs')"},
            },
            "required": ["pattern"],
        },
        "permission": "read",
    },
]


# ── Security ──


def _is_sensitive(path: str) -> bool:
    """Check if a file path is sensitive."""
    basename = os.path.basename(path).lower()
    if basename in SENSITIVE_FILES:
        return True
    _, ext = os.path.splitext(basename)
    if ext in SENSITIVE_EXTENSIONS:
        return True
    return False


def _resolve_path(path: str, cwd: Path) -> Path:
    """Resolve a path relative to cwd if not absolute."""
    p = Path(path)
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def _cap_output(text: str) -> str:
    """Truncate output to MAX_OUTPUT_SIZE."""
    if len(text) > MAX_OUTPUT_SIZE:
        return text[:MAX_OUTPUT_SIZE] + "\n... (truncated)"
    return text


# ── Executors ──


def exec_read_file(args: dict, cwd: Path) -> ToolResult:
    """Read file contents with optional offset/limit."""
    path = _resolve_path(args.get("path", ""), cwd)

    if _is_sensitive(str(path)):
        return ToolResult(False, f"Cannot read sensitive file: {path.name}")

    if not path.is_file():
        return ToolResult(False, f"File not found: {args.get('path', '')}")

    if path.stat().st_size > MAX_FILE_SIZE:
        return ToolResult(False, f"File too large (max {MAX_FILE_SIZE // 1_000_000}MB): {path.name}")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return ToolResult(False, f"Cannot read file: {e}")

    offset = args.get("offset", 0)
    limit = args.get("limit", DEFAULT_READ_LIMIT)

    selected = lines[offset:offset + limit]
    # Add line numbers
    numbered = [f"{i + offset + 1:4d} | {line}" for i, line in enumerate(selected)]
    output = "\n".join(numbered)

    total = len(lines)
    shown = len(selected)
    header = f"File: {args.get('path', '')} ({total} lines, showing {offset + 1}-{offset + shown})"

    return ToolResult(True, _cap_output(f"{header}\n{output}"))


def _post_fix(text: str) -> str:
    """Apply the same post-fix used on prose responses to tool-arg content.
    Strips deprecated Anchor patterns (declare_id!, coral-xyz, ProgramResult,
    ctx.bumps.get(), `<'info>` lifetimes, etc.) before they reach disk."""
    from sealevel_cli.client import clean_model_response, fix_anchor_code
    return fix_anchor_code(clean_model_response(text))


def exec_write_file(args: dict, cwd: Path) -> ToolResult:
    """Write content to a file."""
    path = _resolve_path(args.get("path", ""), cwd)

    if _is_sensitive(str(path)):
        return ToolResult(False, f"Cannot write sensitive file: {path.name}")

    content = _post_fix(args.get("content", ""))

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as e:
        return ToolResult(False, f"Cannot write file: {e}")

    line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
    return ToolResult(True, f"Wrote {line_count} lines to {args.get('path', '')}")


def exec_edit_file(args: dict, cwd: Path) -> ToolResult:
    """Search and replace text in a file."""
    path = _resolve_path(args.get("path", ""), cwd)

    if _is_sensitive(str(path)):
        return ToolResult(False, f"Cannot edit sensitive file: {path.name}")

    if not path.is_file():
        return ToolResult(False, f"File not found: {args.get('path', '')}")

    old_text = args.get("old_text", "")
    new_text = _post_fix(args.get("new_text", ""))

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return ToolResult(False, f"Cannot read file: {e}")

    if old_text not in content:
        return ToolResult(False, f"Text not found in {args.get('path', '')}: {old_text[:60]}...")

    # Replace first occurrence only
    updated = content.replace(old_text, new_text, 1)

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as e:
        return ToolResult(False, f"Cannot write file: {e}")

    old_lines = old_text.count("\n") + 1
    new_lines = new_text.count("\n") + 1
    return ToolResult(True, f"Edited {args.get('path', '')}: -{old_lines} +{new_lines} lines")


def exec_run_command(args: dict, cwd: Path) -> ToolResult:
    """Execute a shell command."""
    command = args.get("command", "")
    timeout = args.get("timeout", DEFAULT_CMD_TIMEOUT)

    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
        )
        output = ""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr:
            output += ("\n" if output else "") + proc.stderr

        output = _cap_output(output.strip())

        if proc.returncode == 0:
            return ToolResult(True, output or "(no output)")
        else:
            return ToolResult(False, f"Exit code {proc.returncode}\n{output}")
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"Command timed out after {timeout}s: {command}")
    except OSError as e:
        return ToolResult(False, f"Command failed: {e}")


def exec_glob_files(args: dict, cwd: Path) -> ToolResult:
    """Find files matching a glob pattern."""
    pattern = args.get("pattern", "")
    search_path = _resolve_path(args.get("path", "."), cwd)

    if not search_path.is_dir():
        return ToolResult(False, f"Directory not found: {args.get('path', '.')}")

    matches = sorted(search_path.glob(pattern))
    # Filter to files only, make relative
    files = []
    for m in matches:
        if m.is_file():
            try:
                files.append(str(m.relative_to(cwd)))
            except ValueError:
                files.append(str(m))

    if not files:
        return ToolResult(True, f"No matches for pattern: {pattern}")

    output = "\n".join(files[:100])  # Cap at 100 files
    if len(files) > 100:
        output += f"\n... and {len(files) - 100} more"

    return ToolResult(True, f"{len(files)} files found:\n{output}")


def exec_grep_files(args: dict, cwd: Path) -> ToolResult:
    """Search file contents with regex."""
    pattern = args.get("pattern", "")
    search_path = _resolve_path(args.get("path", "."), cwd)
    file_glob = args.get("glob", None)

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return ToolResult(False, f"Invalid regex: {e}")

    if not search_path.exists():
        return ToolResult(False, f"Path not found: {args.get('path', '.')}")

    # Collect files to search
    if search_path.is_file():
        files = [search_path]
    elif file_glob:
        files = sorted(search_path.rglob(file_glob))
    else:
        files = sorted(search_path.rglob("*"))

    matches = []
    for f in files:
        if not f.is_file():
            continue
        if f.stat().st_size > MAX_FILE_SIZE:
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                try:
                    rel = str(f.relative_to(cwd))
                except ValueError:
                    rel = str(f)
                matches.append(f"{rel}:{i}: {line.strip()}")
                if len(matches) >= 50:  # Cap at 50 matches
                    break
        if len(matches) >= 50:
            break

    if not matches:
        return ToolResult(True, f"No matches for pattern: {pattern}")

    output = "\n".join(matches)
    if len(matches) >= 50:
        output += "\n... (results capped at 50)"

    return ToolResult(True, _cap_output(output))


# ── Dispatcher ──


_EXECUTORS = {
    "read_file": exec_read_file,
    "write_file": exec_write_file,
    "edit_file": exec_edit_file,
    "run_command": exec_run_command,
    "glob_files": exec_glob_files,
    "grep_files": exec_grep_files,
}


def execute(name: str, args: dict, cwd: Path) -> ToolResult:
    """Execute a tool by name."""
    executor = _EXECUTORS.get(name)
    if not executor:
        available = ", ".join(sorted(_EXECUTORS.keys()))
        return ToolResult(False, f"Unknown tool: {name}. Available: {available}")
    return executor(args, cwd=cwd)
