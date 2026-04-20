#!/usr/bin/env python3
"""Collect high-quality Solana Rust code from open-source repos and produce SFT training data.

Clones curated MIT/Apache-2.0 Solana repos, parses .rs files to extract functions,
structs, impl blocks, and instruction handlers, then generates ChatML SFT examples
in JSONL format.

Usage:
    python scripts/collect_solana_code.py                  # run full pipeline
    python scripts/collect_solana_code.py --skip-clone     # skip cloning, reuse existing
    python scripts/collect_solana_code.py --list            # list configured repos
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
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
OUTPUT_FILE = OUTPUT_DIR / "solana_code_sft.jsonl"

SYSTEM_PROMPT = (
    "You are Sealevel, an expert Solana and Anchor development assistant. "
    "Provide accurate, secure, and up-to-date code using modern Anchor 0.30+ "
    "patterns (solana-foundation/anchor, InitSpace, ctx.bumps.field_name). "
    "When uncertain, say so rather than guessing. Never suggest reentrancy "
    "guards (Solana prevents reentrancy via CPI depth limits). Never reference "
    "coral-xyz/anchor or declare_id! — these are deprecated."
)

# Minimum / maximum line counts for files to include
MIN_LINES = 50
MIN_LINES_PINOCCHIO = 20  # Pinocchio programs are more concise
MAX_LINES = 500

# ---------------------------------------------------------------------------
# Repository definitions
# ---------------------------------------------------------------------------

@dataclass
class RepoSource:
    """A GitHub repo and the subdirectory paths to collect from."""

    owner_repo: str  # e.g. "coral-xyz/anchor"
    subdirs: list[str] = field(default_factory=list)  # empty = whole repo
    license: str = "Apache-2.0"

    @property
    def name(self) -> str:
        return self.owner_repo.replace("/", "_")

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner_repo}.git"


REPOS: list[RepoSource] = [
    # ═══════════════════════════════════════════════════════════════════════════
    # CORE FRAMEWORKS & EXAMPLES
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("solana-developers/program-examples", ["basics", "tokens", "compression"], "Apache-2.0"),
    RepoSource("solana-developers/anchor-examples", [], "Apache-2.0"),
    RepoSource("solana-developers/developer-bootcamp-2024", [], "MIT"),
    RepoSource("coral-xyz/anchor", ["examples", "tests"], "Apache-2.0"),
    RepoSource("solana-foundation/anchor", ["examples", "tests"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # PINOCCHIO FRAMEWORK
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("anza-xyz/pinocchio", ["sdk/pinocchio/src", "examples"], "Apache-2.0"),
    RepoSource("vict0rcarvalh0/pinocchio-guide", [], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # CORE SDK & PROGRAMS
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("anza-xyz/solana-sdk", ["sdk/program/src", "sdk/pubkey/src", "sdk/instruction/src"], "Apache-2.0"),
    RepoSource("solana-program/token", ["program/src"], "Apache-2.0"),
    RepoSource("solana-program/token-2022", ["program/src"], "Apache-2.0"),
    RepoSource("solana-program/associated-token-account", ["program/src"], "Apache-2.0"),
    RepoSource("solana-program/memo", ["program/src"], "Apache-2.0"),
    RepoSource("solana-program/stake", ["program/src"], "Apache-2.0"),
    RepoSource("solana-program/system", ["program/src"], "Apache-2.0"),
    RepoSource("solana-labs/solana-program-library", ["token", "governance", "stake-pool", "account-compression", "name-service", "token-lending"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # DEX & AMM PROTOCOLS
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("raydium-io/raydium-clmm", ["programs/amm/src"], "Apache-2.0"),
    RepoSource("raydium-io/raydium-cp-swap", ["programs/cp-swap/src"], "Apache-2.0"),
    RepoSource("raydium-io/raydium-amm", ["program/src"], "Apache-2.0"),
    RepoSource("orca-so/whirlpools", ["programs/whirlpool/src"], "Apache-2.0"),
    RepoSource("openbook-dex/openbook-v2", ["programs/openbook-v2/src"], "Apache-2.0"),
    RepoSource("openbook-dex/program", ["dex/src"], "Apache-2.0"),
    RepoSource("Ellipsis-Labs/phoenix-v1", ["src"], "Apache-2.0"),
    RepoSource("saber-hq/stable-swap", ["stable-swap-program"], "Apache-2.0"),
    RepoSource("saber-hq/saber-common", ["programs"], "Apache-2.0"),
    RepoSource("invariant-labs/protocol", ["programs"], "Apache-2.0"),
    RepoSource("GooseFX1/gamma-swap", ["programs"], "MIT"),
    RepoSource("aldrin-labs/CLOB", ["programs"], "Apache-2.0"),
    RepoSource("mercurial-finance/stable-swap-n-pool-instructions", ["programs"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # PERPETUALS & DERIVATIVES
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("drift-labs/protocol-v2", ["programs/drift/src"], "Apache-2.0"),
    RepoSource("drift-labs/jit-proxy", ["programs"], "MIT"),
    RepoSource("blockworks-foundation/mango-v4", ["programs"], "Apache-2.0"),
    RepoSource("zetamarkets/fuze", ["programs"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # LENDING & BORROWING
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("mrgnlabs/marginfi-v2", ["programs"], "Apache-2.0"),
    RepoSource("Kamino-Finance/klend", ["programs"], "Apache-2.0"),
    RepoSource("Kamino-Finance/kfarms", ["programs"], "Apache-2.0"),
    RepoSource("solendprotocol/solana-program-library", ["token-lending/program/src"], "Apache-2.0"),
    RepoSource("port-finance/variable-rate-lending", ["programs"], "Apache-2.0"),
    RepoSource("jet-lab/jet-v2", ["programs"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # LIQUID STAKING
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("marinade-finance/liquid-staking-program", ["programs/marinade-finance/src"], "Apache-2.0"),
    RepoSource("marinade-finance/validator-bonds", ["programs"], "MIT"),
    RepoSource("jito-foundation/stakenet", ["programs/steward", "programs/validator-history"], "Apache-2.0"),
    RepoSource("jito-foundation/distributor", ["programs"], "MIT"),
    RepoSource("jito-foundation/jito-solana-program-library", ["programs"], "Apache-2.0"),
    RepoSource("ChorusOne/solido", ["program/src"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # NFT & METAPLEX
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("metaplex-foundation/mpl-token-metadata", ["programs/token-metadata/program/src"], "Apache-2.0"),
    RepoSource("metaplex-foundation/mpl-candy-machine", ["programs/candy-machine-core", "programs/candy-guard"], "Apache-2.0"),
    RepoSource("metaplex-foundation/mpl-bubblegum", ["programs/bubblegum/program/src"], "Apache-2.0"),
    RepoSource("metaplex-foundation/mpl-toolbox", ["programs"], "Apache-2.0"),
    RepoSource("tensor-foundation/toolbox", ["programs"], "MIT"),

    # ═══════════════════════════════════════════════════════════════════════════
    # ORACLES & DATA FEEDS
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("pyth-network/pyth-sdk-rs", ["pyth-sdk-solana/src"], "Apache-2.0"),
    RepoSource("pyth-network/pyth-crosschain", ["target_chains/solana"], "Apache-2.0"),
    RepoSource("switchboard-xyz/solana-sdk", ["programs"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # GOVERNANCE & MULTISIG
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("Squads-Protocol/v4", ["programs"], "Apache-2.0"),
    RepoSource("Squads-Protocol/squads-mpl", ["programs"], "Apache-2.0"),
    RepoSource("coral-xyz/multisig", ["programs"], "Apache-2.0"),
    RepoSource("solana-labs/governance-program-library", ["programs"], "Apache-2.0"),
    RepoSource("blockworks-foundation/voter-stake-registry", ["programs"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # CROSS-CHAIN & BRIDGES
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("wormhole-foundation/wormhole", ["solana/bridge/program", "solana/token_bridge"], "Apache-2.0"),
    RepoSource("wormhole-foundation/native-token-transfers", ["solana"], "Apache-2.0"),
    RepoSource("debridge-finance/debridge-solana-sdk", ["src", "example-program"], "MIT"),

    # ═══════════════════════════════════════════════════════════════════════════
    # INFRASTRUCTURE & AUTOMATION
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("clockwork-xyz/clockwork", ["programs"], "MIT"),
    RepoSource("nosana-ci/nosana-programs", ["programs"], "MIT"),
    RepoSource("Lightprotocol/light-protocol", ["programs/system", "programs/compressed-token"], "Apache-2.0"),
    RepoSource("helius-labs/helius-rust-sdk", ["src"], "MIT"),

    # ═══════════════════════════════════════════════════════════════════════════
    # DePIN & IOT
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("helium/helium-program-library", [
        "programs/circuit-breaker", "programs/lazy-distributor",
        "programs/voter-stake-registry", "programs/fanout",
        "programs/treasury-management",
    ], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # STABLECOINS & TOKEN PROGRAMS
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("UXDProtocol/uxd-program", ["programs"], "Apache-2.0"),
    RepoSource("bonfida/token-vesting", ["program/src"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # ESCROW & UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("ironaddicteddog/anchor-escrow", ["programs"], "MIT"),
    RepoSource("GokiProtocol/goki", ["programs/smart-wallet"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # PRIVACY & SECURITY
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("elusiv-privacy/elusiv", ["programs"], "Apache-2.0"),
    RepoSource("civicteam/token-guard", ["program/src"], "Apache-2.0"),

    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGING & SOCIAL
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("dialectlabs/protocol", ["programs"], "MIT"),

    # ═══════════════════════════════════════════════════════════════════════════
    # GAMING & NFT MARKETPLACES
    # ═══════════════════════════════════════════════════════════════════════════
    RepoSource("Aurory-Game/comptoir", ["programs"], "MIT"),
]

# Repos where test files are instructional and should NOT be skipped
_INCLUDE_TESTS_REPOS = {
    "solana-developers/anchor-examples",
    "vict0rcarvalh0/pinocchio-guide",
}

# Repos that use Pinocchio framework (lower MIN_LINES threshold)
_PINOCCHIO_REPOS = {
    "anza-xyz/pinocchio",
    "vict0rcarvalh0/pinocchio-guide",
}

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


def collect_rs_files(repo_path: Path, subdirs: list[str]) -> list[Path]:
    """Return list of .rs files under the given subdirectories of a repo."""
    roots = [repo_path / sd for sd in subdirs] if subdirs else [repo_path]
    rs_files: list[Path] = []
    for root in roots:
        if not root.exists():
            console.print(f"    [yellow]Subdir not found: {root}[/yellow]")
            continue
        for f in root.rglob("*.rs"):
            rs_files.append(f)
    return rs_files


def passes_quality_filter(
    path: Path, content: str, *, repo_owner_repo: str = ""
) -> bool:
    """Return True if the file should be included in training data."""
    lines = content.splitlines()
    line_count = len(lines)

    # Line count bounds — lower threshold for Pinocchio repos
    min_lines = MIN_LINES_PINOCCHIO if repo_owner_repo in _PINOCCHIO_REPOS else MIN_LINES
    if line_count < min_lines or line_count > MAX_LINES:
        return False

    # Skip test-only files (unless repo is in the include-tests list)
    if repo_owner_repo not in _INCLUDE_TESTS_REPOS:
        if "/test/" in str(path) or "/tests/" in str(path):
            return False
    # Skip files that are entirely test modules
    if "#[cfg(test)]" in content and content.strip().startswith("#[cfg(test)]"):
        return False

    # Skip auto-generated files
    lower = content[:500].lower()
    if "auto-generated" in lower or "autogenerated" in lower or "do not edit" in lower:
        return False

    return True


# ---------------------------------------------------------------------------
# Rust parsing — extract code units
# ---------------------------------------------------------------------------

@dataclass
class CodeUnit:
    """A single extractable code unit from a Rust file."""

    kind: str  # "function" | "struct" | "enum" | "impl" | "instruction"
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


# Patterns that identify code unit start lines
_FN_RE = re.compile(r"^(\s*)(pub\s+)?(fn\s+(\w+))")
_STRUCT_RE = re.compile(r"^(\s*)(pub\s+)?struct\s+(\w+)")
_ENUM_RE = re.compile(r"^(\s*)(pub\s+)?enum\s+(\w+)")
_IMPL_RE = re.compile(r"^(\s*)impl\b.*\{")
_INSTRUCTION_RE = re.compile(
    r"^(\s*)(pub\s+)?fn\s+(\w+)\s*\(\s*ctx\s*:\s*Context<",
)
# Pinocchio entrypoint pattern: fn process_instruction(program_id, accounts, data)
_PINOCCHIO_ENTRYPOINT_RE = re.compile(
    r"^(\s*)(pub\s+)?fn\s+(process_instruction)\s*\(",
)


def extract_code_units(content: str) -> list[CodeUnit]:
    """Parse a Rust source file and extract functions, structs, enums, and impl blocks."""
    lines = content.splitlines()
    units: list[CodeUnit] = []
    seen_spans: set[tuple[int, int]] = set()  # avoid duplicates

    for line_idx, line in enumerate(lines):
        # --- Anchor instruction handlers (special case of fn) ---
        m = _INSTRUCTION_RE.match(line)
        if m:
            fn_name = m.group(3)
            brace_start = content.find("{", sum(len(l) + 1 for l in lines[:line_idx]))
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            # Walk back to get attribute lines
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
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span = (attr_start, brace_end)
            if span not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("instruction", fn_name, snippet, doc))
            continue

        # --- Pinocchio entrypoints ---
        m = _PINOCCHIO_ENTRYPOINT_RE.match(line)
        if m:
            fn_name = m.group(3)
            brace_start = content.find("{", sum(len(l) + 1 for l in lines[:line_idx]))
            if brace_start == -1:
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
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
            code_start = sum(len(l) + 1 for l in lines[:attr_start])
            snippet = content[code_start : brace_end + 1].strip()
            span = (attr_start, brace_end)
            if span not in seen_spans and len(snippet.splitlines()) >= 3:
                seen_spans.add(span)
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("instruction", fn_name, snippet, doc))
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
                # Tuple struct or unit struct on a single line — skip if trivial
                continue
            brace_end = _find_matching_brace(content, brace_start)
            if brace_end == -1:
                continue
            # Include attributes above
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

        # --- Enums ---
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
                # Extract name from impl header
                header = line.strip()
                impl_name = header.replace("{", "").strip()
                doc = _collect_doc_comment(lines, line_idx)
                units.append(CodeUnit("impl", impl_name, snippet, doc))

    return units


# ---------------------------------------------------------------------------
# Prompt generation
# ---------------------------------------------------------------------------


def _snake_to_natural(name: str) -> str:
    """Convert snake_case to a natural phrase: 'process_deposit' -> 'process deposit'."""
    return name.replace("_", " ")


def _is_pinocchio_repo(repo_name: str) -> bool:
    return repo_name in _PINOCCHIO_REPOS


def generate_prompt_for_unit(unit: CodeUnit, repo_name: str) -> str:
    """Generate a realistic user prompt for a code unit."""
    natural_name = _snake_to_natural(unit.name)
    is_pinocchio = _is_pinocchio_repo(repo_name)
    framework = "Pinocchio" if is_pinocchio else "Anchor"

    if unit.kind == "instruction":
        if unit.name == "process_instruction":
            # Pinocchio entrypoint
            if unit.doc_comment:
                return (
                    f"Write a Pinocchio (zero-copy) Solana program entrypoint that "
                    f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
                )
            return f"Write a Pinocchio process_instruction entrypoint for a Solana program."
        if unit.doc_comment:
            return (
                f"Write an {framework} instruction handler called `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Write an {framework} instruction handler for `{unit.name}` in a Solana program."

    if unit.kind == "function":
        if unit.doc_comment:
            return (
                f"Implement a Rust function `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Write a Rust function called `{unit.name}` for a Solana program that performs {natural_name}."

    if unit.kind == "struct":
        # Try to extract field names from the snippet
        field_matches = re.findall(r"pub\s+(\w+)\s*:", unit.code)
        if field_matches:
            fields_str = ", ".join(f"`{f}`" for f in field_matches[:6])
            return (
                f"Define an Anchor account struct `{unit.name}` with fields {fields_str} "
                f"for a Solana program."
            )
        if unit.doc_comment:
            return (
                f"Implement the `{unit.name}` struct that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Implement the `{unit.name}` struct for a Solana program."

    if unit.kind == "enum":
        if unit.doc_comment:
            return (
                f"Define an enum `{unit.name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Define an enum `{unit.name}` for a Solana program."

    if unit.kind == "impl":
        # impl blocks — extract the type name
        type_match = re.match(r"impl(?:<[^>]+>)?\s+(\w+)", unit.name)
        type_name = type_match.group(1) if type_match else unit.name
        if unit.doc_comment:
            return (
                f"Write the implementation block for `{type_name}` that "
                f"{unit.doc_comment[0].lower()}{unit.doc_comment[1:]}."
            )
        return f"Show how to implement methods for `{type_name}` in a Solana program."

    return f"Write the following Solana Rust code from {repo_name}."


def generate_file_prompt(file_path: Path, repo_source: RepoSource) -> str:
    """Generate a user prompt for a whole-file training example."""
    rel = file_path.relative_to(RAW_DIR / repo_source.name)
    parts = list(rel.parts)

    # Heuristic: use directory context
    if "instructions" in parts or "instruction" in parts:
        return (
            f"Write a complete Anchor instructions module for a Solana program "
            f"(from {repo_source.owner_repo}, file: {rel})."
        )
    if "state" in parts:
        return (
            f"Write the program state definitions for a Solana program "
            f"(from {repo_source.owner_repo}, file: {rel})."
        )
    if "lib.rs" in parts:
        return (
            f"Write the main lib.rs entry point for a Solana Anchor program "
            f"(from {repo_source.owner_repo})."
        )

    stem = file_path.stem
    return (
        f"Write a complete Solana Rust module `{stem}` "
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

    if not passes_quality_filter(
        file_path, content, repo_owner_repo=repo_source.owner_repo
    ):
        return []

    records: list[dict] = []

    # 1. Whole-file example
    file_prompt = generate_file_prompt(file_path, repo_source)
    records.append(make_sft_record(SYSTEM_PROMPT, file_prompt, content.strip()))

    # 2. Code-unit examples
    units = extract_code_units(content)
    for unit in units:
        prompt = generate_prompt_for_unit(unit, repo_source.owner_repo)
        records.append(make_sft_record(SYSTEM_PROMPT, prompt, unit.code))

    return records


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main(
    skip_clone: bool = typer.Option(False, "--skip-clone", help="Skip cloning repos"),
    list_repos: bool = typer.Option(False, "--list", help="List configured repos and exit"),
):
    """Collect Solana Rust code from GitHub repos and produce SFT training data."""
    if list_repos:
        console.print("[bold]Configured repositories:[/bold]")
        for r in REPOS:
            subdirs = ", ".join(r.subdirs) if r.subdirs else "(whole repo)"
            console.print(f"  {r.owner_repo:45s}  {r.license:12s}  {subdirs}")
        raise typer.Exit()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Phase 1 — Clone
    if not skip_clone:
        console.print("\n[bold blue]Phase 1: Cloning repositories[/bold blue]")
        for source in track(REPOS, description="Cloning repos..."):
            clone_repo(source)
    else:
        console.print("\n[dim]Skipping clone phase (--skip-clone)[/dim]")

    # Phase 2 — Collect and parse
    console.print("\n[bold blue]Phase 2: Collecting and parsing Rust files[/bold blue]")

    all_records: list[dict] = []
    total_files = 0
    total_units = 0

    for source in REPOS:
        repo_path = RAW_DIR / source.name
        if not repo_path.exists():
            console.print(f"  [yellow]Repo not found: {source.name} — skipping[/yellow]")
            continue

        rs_files = collect_rs_files(repo_path, source.subdirs)
        console.print(
            f"  {source.owner_repo}: {len(rs_files)} .rs files found"
        )

        for fpath in rs_files:
            records = process_file(fpath, source)
            if records:
                total_files += 1
                # First record is file-level, rest are code units
                total_units += len(records) - 1
                all_records.extend(records)

    # Phase 3 — Write output
    console.print(f"\n[bold blue]Phase 3: Writing output[/bold blue]")
    console.print(f"  Files processed: {total_files}")
    console.print(f"  Code unit examples: {total_units}")
    console.print(f"  Total SFT records: {len(all_records)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    console.print(f"\n[bold green]Done![/bold green] Output: {OUTPUT_FILE}")
    console.print(
        f"  File size: {OUTPUT_FILE.stat().st_size / 1_048_576:.1f} MB"
    )


if __name__ == "__main__":
    app()
