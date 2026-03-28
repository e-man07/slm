"""Shared schema and utilities for the SLM data pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Record:
    """Standard intermediate format for all pipeline data."""

    id: str  # SHA-256 of content
    source: str  # e.g. "github/solana-foundation/anchor"
    source_type: str  # code | docs | qa | synthetic
    content: str
    language: str  # rust | ts | md | toml
    license: str  # SPDX identifier
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def make_id(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> Record:
        return cls(**d)


LANG_EXTENSIONS = {
    ".rs": "rust",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "js",
    ".md": "md",
    ".mdx": "md",
    ".toml": "toml",
    ".json": "json",
}

# Files/dirs to skip during collection
SKIP_PATTERNS = {
    "node_modules",
    "target",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".next",
    "package-lock.json",
    "yarn.lock",
    "Cargo.lock",
}


def detect_language(path: Path) -> str | None:
    return LANG_EXTENSIONS.get(path.suffix.lower())


def detect_anchor_version(content: str, file_path: str = "") -> str | None:
    """Extract anchor-lang version from Cargo.toml content or nearby context."""
    # Direct Cargo.toml match
    m = re.search(r'anchor-lang\s*=\s*"([^"]+)"', content)
    if m:
        return m.group(1)
    # Version in dependency table
    m = re.search(r'anchor-lang\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', content)
    if m:
        return m.group(1)
    return None


def is_modern_anchor(content: str) -> bool:
    """Check if code uses modern Anchor 0.30+ patterns."""
    modern_markers = ["declare_program!", "solana-foundation/anchor"]
    old_markers = ["declare_id!", "coral-xyz/anchor"]
    has_modern = any(m in content for m in modern_markers)
    has_old = any(m in content for m in old_markers)
    if has_modern and not has_old:
        return True
    return False


def normalize_for_hashing(content: str, language: str) -> str:
    """Normalize code content before hashing for dedup.

    Strips comments and normalizes whitespace for code files.
    """
    if language == "rust":
        # Strip single-line comments
        content = re.sub(r"//[^\n]*", "", content)
        # Strip block comments (non-greedy)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    elif language in ("ts", "js"):
        content = re.sub(r"//[^\n]*", "", content)
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

    # Normalize whitespace
    content = re.sub(r"\s+", " ", content).strip()
    return content


def write_jsonl(records: list[Record], path: Path) -> int:
    """Write records to JSONL file. Returns count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(r.to_json() + "\n")
            count += 1
    return count


def read_jsonl(path: Path) -> list[Record]:
    """Read records from JSONL file."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(Record.from_dict(json.loads(line)))
    return records


def today_str() -> str:
    return date.today().isoformat()
