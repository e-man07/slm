"""Tests for sealevel_cli.storage — local JSONL session backup."""
import json
import os
import tempfile
import time
import pytest
from pathlib import Path

from sealevel_cli.storage import SessionStorage


def test_create_and_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        s.create("test-123")
        assert (Path(tmpdir) / "test-123.jsonl").exists()


def test_append_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        s.create("sess-1")
        s.append("sess-1", "user", "hello")
        s.append("sess-1", "assistant", "hi there")
        msgs = s.load("sess-1")
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi there"}


def test_load_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        assert s.load("nonexistent") == []


def test_load_skips_corrupt_lines():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        path = Path(tmpdir) / "corrupt.jsonl"
        with open(path, "w") as f:
            f.write('{"role":"user","content":"good","ts":"2026-01-01"}\n')
            f.write('CORRUPT LINE\n')
            f.write('{"role":"assistant","content":"also good","ts":"2026-01-01"}\n')
        msgs = s.load("corrupt")
        assert len(msgs) == 2


def test_list_sessions_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        assert s.list_sessions() == []


def test_list_sessions_ordered_by_mtime():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        s.create("old")
        time.sleep(0.05)
        s.create("new")
        s.append("new", "user", "latest")
        sessions = s.list_sessions()
        assert sessions[0] == "new"


def test_latest_session_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        assert s.latest_session_id() is None
        s.create("sess-1")
        assert s.latest_session_id() == "sess-1"


def test_path_traversal_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        with pytest.raises(ValueError, match="Invalid session ID"):
            s.create("../../etc/passwd")


def test_path_traversal_slash_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        with pytest.raises(ValueError, match="Invalid session ID"):
            s.append("foo/bar", "user", "test")


def test_path_traversal_backslash_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = SessionStorage(base_dir=Path(tmpdir))
        with pytest.raises(ValueError, match="Invalid session ID"):
            s.load("foo\\bar")


def test_append_creates_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir) / "deep" / "sessions"
        s = SessionStorage(base_dir=nested)
        s.append("auto", "user", "test")
        assert (nested / "auto.jsonl").exists()
