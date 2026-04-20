#!/usr/bin/env python3
"""Collect Pinocchio framework Solana code from open-source repos and produce SFT training data.

Pinocchio (anza-xyz/pinocchio) is a zero-copy, zero-dependency framework for
high-performance Solana programs. It uses raw process_instruction entrypoints,
manual AccountInfo parsing, and manual discriminator handling instead of
Anchor macros.

This script is the Pinocchio counterpart to collect_solana_code.py, tuned for
Pinocchio-specific patterns and the characteristically concise program style.

Usage:
    python scripts/collect_pinocchio.py                  # run full pipeline
    python scripts/collect_pinocchio.py --skip-clone     # skip cloning, reuse existing
    python scripts/collect_pinocchio.py --list            # list configured repos
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track

app = typer.Typer(invoke_without_command=True)
console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "repos"
OUTPUT_DIR = PROJECT_ROOT / "data" / "collected"
OUTPUT_FILE = OUTPUT_DIR / "pinocchio_sft.jsonl"

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana development assistant. Provide accurate "
    "code using Pinocchio (anza-xyz/pinocchio), a zero-copy, zero-dependency "
    "framework for high-performance Solana programs. When uncertain, say so "
    "rather than guessing."
)

# Pinocchio programs are concise — lower minimum than Anchor
MIN_LINES = 20
MAX_LINES = 500

# Whole-file examples for programs under this threshold
WHOLE_FILE_MAX_LINES = 200

# ---------------------------------------------------------------------------
# Repository definitions
# ---------------------------------------------------------------------------


@dataclass
class RepoSource:
    """A GitHub repo and the subdirectory paths to collect from."""

    owner_repo: str  # e.g. "anza-xyz/pinocchio"
    subdirs: list[str] = field(default_factory=list)  # empty = whole repo
    license: str = "Apache-2.0"

    @property
    def name(self) -> str:
        return self.owner_repo.replace("/", "_")

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner_repo}.git"


REPOS: list[RepoSource] = [
    RepoSource(
        "anza-xyz/pinocchio",
        ["sdk/pinocchio/src", "examples"],
        "Apache-2.0",
    ),
    RepoSource(
        "vict0rcarvalh0/pinocchio-guide",
        [],  # whole repo
        "Apache-2.0",
    ),
    RepoSource(
        "solana-developers/program-examples",
        [],  # we filter to */pinocchio/* paths below
        "Apache-2.0",
    ),
]


# ---------------------------------------------------------------------------
# Cloning helpers
# ---------------------------------------------------------------------------


def clone_repo(source: RepoSource) -> Path:
    """Shallow-clone a repo. Returns path to cloned directory."""
    dest = RAW_DIR / source.name
    if dest.exists():
        console.print(f"  [dim]Already cloned: {source.name}, pulling latest...[/dim]")
        subprocess.run(
            ["git", "-C", str(dest), "pull", "--ff-only"],
            capture_output=True,
        )
        return dest

    console.print(f"  Cloning {source.clone_url}...")
    token = os.environ.get("GITHUB_TOKEN")
    url = source.clone_url
    if token:
        url = url.replace("https://", f"https://x-access-token:{token}@")

    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"  [red]Failed to clone {source.name}: {result.stderr.strip()}[/red]")
        return dest  # return path anyway; caller checks existence
    return dest


# ---------------------------------------------------------------------------
# Rust file discovery and filtering
# ---------------------------------------------------------------------------


def collect_rs_files(repo_path: Path, source: RepoSource) -> list[Path]:
    """Return list of .rs files under the given subdirectories of a repo.

    For solana-developers/program-examples, only collect files under
    */pinocchio/* paths.
    """
    roots = [repo_path / sd for sd in source.subdirs] if source.subdirs else [repo_path]
    rs_files: list[Path] = []
    for root in roots:
        if not root.exists():
            console.print(f"    [yellow]Subdir not found: {root}[/yellow]")
            continue
        for f in root.rglob("*.rs"):
            # For program-examples, only collect Pinocchio subdirs
            if source.owner_repo == "solana-developers/program-examples":
                rel = str(f.relative_to(repo_path))
                if "/pinocchio/" not in rel and not rel.startswith("pinocchio/"):
                    continue
            rs_files.append(f)
    return rs_files


def passes_quality_filter(path: Path, content: str) -> bool:
    """Return True if the file should be included in training data."""
    lines = content.splitlines()
    line_count = len(lines)

    if line_count < MIN_LINES or line_count > MAX_LINES:
        return False

    # Skip files that are entirely test modules (but include test files generally)
    if "#[cfg(test)]" in content and content.strip().startswith("#[cfg(test)]"):
        return False

    # Skip auto-generated files
    lower = content[:500].lower()
    if "auto-generated" in lower or "autogenerated" in lower or "do not edit" in lower:
        return False

    return True


# ---------------------------------------------------------------------------
# Rust parsing — extract code units (adapted for Pinocchio patterns)
# ---------------------------------------------------------------------------


@dataclass
class CodeUnit:
    """A single extractable code unit from a Rust file."""

    kind: str  # "function" | "struct" | "enum" | "impl" | "instruction" | "error_enum" | "unsafe_impl"
    name: str
    code: str
    doc_comment: str = ""


def _collect_doc_comment(lines: list[str], start_idx: int) -> str:
    """Walk backwards from start_idx to collect contiguous /// or //! doc comments."""
    doc_lines: list[str] = []
    i = start_idx - 1
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("///") or stripped.startswith("//!"):
            doc_lines.insert(0, stripped.lstrip("/!").strip())
            i -= 1
        elif stripped.startswith("#["):
            # skip attributes, keep looking for doc comments above
            i -= 1
        elif stripped == "":
            break
        else:
            break
    return " ".join(doc_lines).strip()


def _find_matching_brace(text: str, start: int) -> int:
    """Find the index of the closing brace matching the opening brace at `start`."""
    depth = 0
    in_string = False
    escape_next = False
    in_line_comment = False
    in_block_comment = False
    i = start
    while i < len(text):
        ch = text[i]

        if escape_next:
            escape_next = False
            i += 1
            continue

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and i + 1 < len(text) and text[i + 1] == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if ch == "\\" and in_string:
            escape_next = True
            i += 1
            continue

        if ch == '"' and not in_string:
            in_string = True
            i += 1
            continue
        if ch == '"' and in_string:
            in_string = False
            i += 1
            continue

        if not in_string:
            if ch == "/" and i + 1 < len(text):
                nxt = text[i + 1]
                if nxt == "/":
                    in_line_comment = True
                    i += 2
                    continue
                if nxt == "*":
                    in_block_comment = True
                    i += 2
                    continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i

        i += 1
    return -1


def _walk_back_to_attrs(lines: list[str], line_idx: int) -> int:
    """Walk backwards from line_idx to include attributes and doc comments."""
    attr_start = line_idx
    while attr_start > 0 and (
        lines[attr_start - 1].strip().startswith("#[")
        or lines[attr_start - 1].strip().startswith("///")
        or lines[attr_start - 1].strip().startswith("//!")
        or lines[attr_start - 1].strip() == ""
    ):
        attr_start -= 1
        if lines[attr_start].strip() == "":
            attr_start += 1
            break
    return attr_start


# Patterns that identify code unit start lines
_FN_RE = re.compile(r"^(\s*)(pub\s+)?(fn\s+(\w+))")
_STRUCT_RE = re.compile(r"^(\s*)(pub\s+)?struct\s+(\w+)")
_ENUM_RE = re.compile(r"^(\s*)(pub\s+)?enum\s+(\w+)")
_IMPL_RE = re.compile(r"^(\s*)impl\b.*\{")
_UNSAFE_IMPL_RE = re.compile(r"^(\s*)unsafe\s+impl\b.*\{")

# Pinocchio-specific patterns
_PROCESS_INSTRUCTION_RE = re.compile(
    r"^(\s*)(pub\s+)?fn\s+(process_instruction)\s*\(",
)
_INSTRUCTION_PROCESSOR_RE = re.compile(
    r"^(\s*)(pub\s+)?fn\s+(process_\w+|handle_\w+)\s*\(",
)
_ERROR_ENUM_RE = re.compile(
    r"^(\s*)(pub\s+)?enum\s+(\w*[Ee]rror\w*)",
)


def extract_code_units(content: str) -> list[CodeUnit]:
    """Parse a Rust source file and extract functions, structs, enums, and impl blocks.

    Tuned for Pinocchio patterns: process_instruction entrypoints, unsafe impls,
    instruction processor functions, and custom error enums.
    """
    lines = content.splitlines()
    units: list[CodeUnit] = []
    seen_spans: set[tuple[int, int]] = set()

    for line_idx, line in enumerate(lines):

        # --- process_instruction entrypoints (highest priority) ---
        m = _PROCESS_INSTRUCTION_RE.match(line)
        if m:
            fn_name = m.group(3)
            brace_start = content.find("{", sum(len(l) + 1 for l in lines[:line_idx]))
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            attr_start = _walk_back_to_attrs(lines, line_idx)
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span = (attr_start, brace_end)
            if span not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("instruction", fn_name, snippet, doc))
            continue

        # --- Instruction processor functions (process_*, handle_*) ---
        m = _INSTRUCTION_PROCESSOR_RE.match(line)
        if m:
            fn_name = m.group(3)
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            attr_start = _walk_back_to_attrs(lines, line_idx)
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span = (attr_start, brace_end)
            if span not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("instruction", fn_name, snippet, doc))
            continue

        # --- unsafe impl blocks (Pinocchio account structs) ---
        m = _UNSAFE_IMPL_RE.match(line)
        if m:
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            snippet = content[offset : brace_end + 1].strip()
            span_key = (offset, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span_key)
                header = line.strip()
                impl_name = header.replace("{", "").strip()
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("unsafe_impl", impl_name, snippet, doc))
            continue

        # --- Custom error enums ---
        m = _ERROR_ENUM_RE.match(line)
        if m:
            enum_name = m.group(3)
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            attr_start = _walk_back_to_attrs(lines, line_idx)
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span_key = (code_start, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span_key)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("error_enum", enum_name, snippet, doc))
            continue

        # --- Regular functions ---
        m = _FN_RE.match(line)
        if m:
            fn_name = m.group(4)
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            snippet = content[offset : brace_end + 1].strip()
            span_key = (offset, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span_key)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("function", fn_name, snippet, doc))
            continue

        # --- Structs ---
        m = _STRUCT_RE.match(line)
        if m:
            struct_name = m.group(3)
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            attr_start = line_idx
            while attr_start > 0 and lines[attr_start - 1].strip().startswith("#["):
                attr_start -= 1
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span_key = (code_start, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span_key)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("struct", struct_name, snippet, doc))
            continue

        # --- Enums (non-error) ---
        m = _ENUM_RE.match(line)
        if m:
            enum_name = m.group(3)
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            attr_start = line_idx
            while attr_start > 0 and lines[attr_start - 1].strip().startswith("#["):
                attr_start -= 1
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span_key = (code_start, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span_key)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("enum", enum_name, snippet, doc))
            continue

        # --- impl blocks ---
        m = _IMPL_RE.match(line)
        if m:
            offset = sum(len(l) + 1 for l in lines[:line_idx])
            brace_start = content.find("{", offset)
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            snippet = content[offset : brace_end + 1].strip()
            span_key = (offset, brace_end)
            if span_key not in seen_spans and len(snippet.splitlines()) >= 5:
                seen_spans.add(span_key)
                header = line.strip()
                impl_name = header.replace("{", "").strip()
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("impl", impl_name, snippet, doc))

    return units


# ---------------------------------------------------------------------------
# Prompt generation (Pinocchio-specific)
# ---------------------------------------------------------------------------


def _snake_to_natural(name: str) -> str:
    """Convert snake_case to a natural phrase: 'process_deposit' -> 'process deposit'."""
    return name.replace("_", " ")


def generate_prompt_for_unit(unit: CodeUnit) -> str:
    """Generate a realistic user prompt for a Pinocchio code unit."""
    natural_name = _snake_to_natural(unit.name)

    if unit.kind == "instruction":
        if unit.name == "process_instruction":
            if unit.doc_comment:
                return (
                    f"Write a Pinocchio (zero-copy) Solana program entrypoint that "
                    f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
                )
            return (
                "Implement a process_instruction entrypoint for a Pinocchio "
                "Solana program."
            )
        # Named processor: process_transfer, handle_deposit, etc.
        if unit.doc_comment:
            return (
                f"Write a Pinocchio instruction processor `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Implement the `{unit.name}` instruction processor for a "
            f"Pinocchio Solana program that performs {natural_name}."
        )

    if unit.kind == "function":
        if unit.doc_comment:
            return (
                f"Implement a Rust function `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Write a Rust function called `{unit.name}` for a Pinocchio "
            f"Solana program that performs {natural_name}."
        )

    if unit.kind == "struct":
        field_matches = re.findall(r"pub\s+(\w+)\s*:", unit.code)
        if field_matches:
            fields_str = ", ".join(f"`{f}`" for f in field_matches[:6])
            return (
                f"Define a Pinocchio account struct `{unit.name}` with fields "
                f"{fields_str} for a zero-copy Solana program."
            )
        if unit.doc_comment:
            return (
                f"Implement the `{unit.name}` struct that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Define the `{unit.name}` account struct for a Pinocchio "
            f"Solana program."
        )

    if unit.kind == "unsafe_impl":
        type_match = re.match(r"unsafe\s+impl(?:<[^>]+>)?\s+\w+\s+for\s+(\w+)", unit.name)
        type_name = type_match.group(1) if type_match else unit.name
        if unit.doc_comment:
            return (
                f"Write the unsafe impl block for `{type_name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Implement the unsafe trait impl for `{type_name}` in a "
            f"Pinocchio Solana program (zero-copy account deserialization)."
        )

    if unit.kind == "error_enum":
        if unit.doc_comment:
            return (
                f"Define a custom error enum `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Define a custom error enum `{unit.name}` for a Pinocchio "
            f"Solana program."
        )

    if unit.kind == "enum":
        if unit.doc_comment:
            return (
                f"Define an enum `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Define an enum `{unit.name}` for a Pinocchio Solana program."

    if unit.kind == "impl":
        type_match = re.match(r"impl(?:<[^>]+>)?\s+(\w+)", unit.name)
        type_name = type_match.group(1) if type_match else unit.name
        if unit.doc_comment:
            return (
                f"Write the implementation block for `{type_name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return (
            f"Show how to implement methods for `{type_name}` in a "
            f"Pinocchio Solana program."
        )

    return "Write the following Pinocchio Solana program code."


def generate_file_prompt(file_path: Path, repo_source: RepoSource) -> str:
    """Generate a user prompt for a whole-file training example."""
    rel = file_path.relative_to(RAW_DIR / repo_source.name)
    parts = list(rel.parts)

    if "examples" in parts:
        example_name = None
        for i, p in enumerate(parts):
            if p == "examples" and i + 1 < len(parts):
                example_name = parts[i + 1]
                break
        if example_name:
            natural = example_name.replace("-", " ").replace("_", " ")
            return (
                f"Write a complete Pinocchio (zero-copy) Solana program that "
                f"implements {natural}."
            )

    if "lib.rs" in parts:
        return (
            f"Write the main lib.rs entry point for a Pinocchio Solana program "
            f"(from {repo_source.owner_repo})."
        )

    if "processor" in str(rel).lower() or "instruction" in str(rel).lower():
        return (
            f"Write a complete Pinocchio instruction processor module "
            f"(from {repo_source.owner_repo}, file: {rel})."
        )

    stem = file_path.stem
    return (
        f"Write a complete Pinocchio Solana Rust module `{stem}` "
        f"(from {repo_source.owner_repo}, file: {rel})."
    )


# ---------------------------------------------------------------------------
# SFT record generation
# ---------------------------------------------------------------------------


def make_sft_record(system: str, user: str, assistant: str) -> dict:
    """Create a ChatML SFT training record."""
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def process_file(
    file_path: Path,
    repo_source: RepoSource,
) -> list[dict]:
    """Process one .rs file and return SFT records."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if not passes_quality_filter(file_path, content):
        return []

    records: list[dict] = []
    line_count = len(content.splitlines())

    # 1. Whole-file example (always include for short Pinocchio programs)
    if line_count <= WHOLE_FILE_MAX_LINES:
        file_prompt = generate_file_prompt(file_path, repo_source)
        records.append(make_sft_record(SYSTEM_PROMPT, file_prompt, content.strip()))

    # 2. Code-unit examples
    units = extract_code_units(content)
    for unit in units:
        prompt = generate_prompt_for_unit(unit)
        records.append(make_sft_record(SYSTEM_PROMPT, prompt, unit.code))

    return records


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    skip_clone: bool = typer.Option(False, "--skip-clone", help="Skip cloning repos"),
    list_repos: bool = typer.Option(False, "--list", help="List configured repos and exit"),
):
    """Collect Pinocchio framework Solana code from GitHub repos and produce SFT training data."""
    if list_repos:
        console.print("[bold]Configured Pinocchio repositories:[/bold]")
        for r in REPOS:
            subdirs = ", ".join(r.subdirs) if r.subdirs else "(whole repo)"
            console.print(f"  {r.owner_repo:50s}  {r.license:12s}  {subdirs}")
        raise typer.Exit()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 1 — Clone
    if not skip_clone:
        console.print("\n[bold blue]Phase 1: Cloning Pinocchio repositories[/bold blue]")
        for source in track(REPOS, description="Cloning repos..."):
            clone_repo(source)
    else:
        console.print("\n[dim]Skipping clone phase (--skip-clone)[/dim]")

    # Phase 2 — Collect and parse
    console.print("\n[bold blue]Phase 2: Collecting and parsing Pinocchio Rust files[/bold blue]")

    all_records: list[dict] = []
    total_files = 0
    total_units = 0
    total_whole_file = 0

    for source in REPOS:
        repo_path = RAW_DIR / source.name
        if not repo_path.exists():
            console.print(f"  [yellow]Repo not found: {source.name} — skipping[/yellow]")
            continue

        rs_files = collect_rs_files(repo_path, source)
        console.print(
            f"  {source.owner_repo}: {len(rs_files)} .rs files found"
        )

        for fpath in rs_files:
            records = process_file(fpath, source)
            if records:
                total_files += 1
                # Count whole-file vs code-unit records
                line_count = len(fpath.read_text(errors="replace").splitlines())
                if line_count <= WHOLE_FILE_MAX_LINES:
                    total_whole_file += 1
                    total_units += len(records) - 1
                else:
                    total_units += len(records)
                all_records.extend(records)

    # Phase 3 — Write output
    console.print(f"\n[bold blue]Phase 3: Writing output[/bold blue]")
    console.print(f"  Files processed: {total_files}")
    console.print(f"  Whole-file examples: {total_whole_file}")
    console.print(f"  Code unit examples: {total_units}")
    console.print(f"  Total SFT records: {len(all_records)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    console.print(f"\n[bold green]Done![/bold green] Output: {OUTPUT_FILE}")
    if OUTPUT_FILE.exists():
        console.print(
            f"  File size: {OUTPUT_FILE.stat().st_size / 1_048_576:.1f} MB"
        )


if __name__ == "__main__":
    app()
