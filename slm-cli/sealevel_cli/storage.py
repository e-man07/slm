"""Local JSONL session storage for Sealevel CLI.

Provides crash-safe local backup of session history alongside server persistence.
Each session stored as a JSONL file at ~/.sealevel/sessions/{session_id}.jsonl.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class SessionStorage:
    """Local JSONL session storage."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path.home() / ".sealevel" / "sessions"

    def create(self, session_id: str) -> None:
        """Create session directory and file."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(session_id)
        path.touch(exist_ok=True)

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session JSONL file."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        }
        with open(self._path(session_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
            f.flush()

    def load(self, session_id: str) -> list[dict[str, str]]:
        """Load all messages from a session file."""
        path = self._path(session_id)
        if not path.exists():
            return []
        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    messages.append({"role": entry["role"], "content": entry["content"]})
                except (json.JSONDecodeError, KeyError):
                    continue  # Skip corrupt lines
        return messages

    def list_sessions(self) -> list[str]:
        """List session IDs sorted by most recent first."""
        if not self.base_dir.exists():
            return []
        files = sorted(
            self.base_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [f.stem for f in files]

    def latest_session_id(self) -> str | None:
        """Return the most recent session ID, or None."""
        sessions = self.list_sessions()
        return sessions[0] if sessions else None

    def _path(self, session_id: str) -> Path:
        # Sanitize: reject path traversal attempts
        if "/" in session_id or "\\" in session_id or ".." in session_id:
            raise ValueError(f"Invalid session ID: {session_id}")
        return self.base_dir / f"{session_id}.jsonl"
