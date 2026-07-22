"""LocalStorage is the only storage backend this suite can test offline.

BlobStorage needs a real Vercel Blob store and a real token — neither exists in CI,
so it's smoke-tested manually against a real store instead (see ui/storage.py's
docstring). These tests are the actual behavioral contract LocalStorage promises the
rest of the app: write/read round-trips, exists(), list_keys() with a prefix filter,
and — the specific bug this module exists to avoid — that constructing a Storage
never touches the filesystem before something actually asks it to write.
"""

from __future__ import annotations

import sys
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "ui"
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))

from storage import LocalStorage  # noqa: E402


def test_constructing_local_storage_creates_nothing(tmp_path):
    root = tmp_path / "uploads"
    LocalStorage(root)
    assert not root.exists(), "the directory must not be created until something writes"


def test_write_then_read_round_trips(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("abc123.png", b"\x89PNG\r\n\x1a\nfake")
    assert store.read_bytes("abc123.png") == b"\x89PNG\r\n\x1a\nfake"


def test_read_missing_key_returns_none(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    assert store.read_bytes("no-such-key.png") is None


def test_exists(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    assert not store.exists("abc123.rig.json")
    store.write_bytes("abc123.rig.json", b"{}")
    assert store.exists("abc123.rig.json")


def test_write_creates_nested_directories(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("nested/dir/file.txt", b"hi")
    assert (tmp_path / "uploads" / "nested" / "dir" / "file.txt").read_bytes() == b"hi"


def test_overwrite_replaces_content(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("abc123.spec.json", b"first")
    store.write_bytes("abc123.spec.json", b"second")
    assert store.read_bytes("abc123.spec.json") == b"second"


def test_list_keys_with_no_prefix_returns_everything(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("abc.rig.json", b"{}")
    store.write_bytes("def.rig.json", b"{}")
    assert store.list_keys() == ["abc.rig.json", "def.rig.json"]


def test_list_keys_filters_by_prefix(tmp_path):
    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("abc.rig.json", b"{}")
    store.write_bytes("abc.guide.html", b"<html></html>")
    store.write_bytes("def.rig.json", b"{}")
    assert store.list_keys("abc.") == ["abc.guide.html", "abc.rig.json"]


def test_list_keys_on_a_directory_that_was_never_created(tmp_path):
    store = LocalStorage(tmp_path / "never-written-to")
    assert store.list_keys() == []
