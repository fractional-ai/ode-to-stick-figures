"""build_from_upload() offline, with rig_from_image() and pipeline.run() faked out.

No API key, no model calls — same philosophy as the rest of the suite. The real
vision/model calls are exercised manually (see the session notes on the one live
timing run against rig_from_image() + pipeline.run() directly, unchanged by this
module); what's tested here is this module's own logic: which branch runs for a
refusal vs an invalid rig vs success, and that a successful build's artifacts
actually land in Storage.
"""

from __future__ import annotations

import sys
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "ui"
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))

import upload_build  # noqa: E402
from storage import LocalStorage  # noqa: E402


def _use_local_storage(monkeypatch, tmp_path):
    """Route this module's storage at a tmp_path LocalStorage instead of ui/uploads/,
    so tests never touch the real local upload directory."""
    store = LocalStorage(tmp_path / "uploads")
    monkeypatch.setattr(upload_build, "default_storage", lambda root: store)
    return store


def test_refusal_is_persisted_and_the_pipeline_never_runs(monkeypatch, tmp_path):
    store = _use_local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        upload_build,
        "rig_from_image",
        lambda doodle: {"refuse": True, "refuse_reason": "no animal in this drawing"},
    )

    def _run_should_not_be_called(*args, **kwargs):
        raise AssertionError("pipeline.run() must not run for a refused drawing")

    monkeypatch.setattr(upload_build, "run", _run_should_not_be_called)

    result = upload_build.build_from_upload(b"\x89PNG\r\n\x1a\nfake", ".png")

    assert result.refused == "no animal in this drawing"
    assert store.read_bytes(f"{result.id}.rig.json") is not None


def test_invalid_rig_is_reported_and_nothing_is_persisted(monkeypatch, tmp_path):
    """Matches the existing precedent in prewarm.py's ensure_rig(): an invalid rig
    (the model's answer doesn't satisfy the contract) isn't a refusal and isn't
    persisted — only a real decline or a real success get a permanent record."""
    store = _use_local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(upload_build, "rig_from_image", lambda doodle: {"parts": []})
    monkeypatch.setattr(upload_build, "validate", lambda spec: ["no parts"])

    def _run_should_not_be_called(*args, **kwargs):
        raise AssertionError("pipeline.run() must not run for an invalid rig")

    monkeypatch.setattr(upload_build, "run", _run_should_not_be_called)

    result = upload_build.build_from_upload(b"fake-bytes", ".jpg")

    assert result.refused == "couldn't build a rig: no parts"
    assert store.list_keys() == []


def test_success_syncs_every_artifact_the_pipeline_wrote(monkeypatch, tmp_path):
    """Stand-in for pipeline.run(): writes the same shape of files run() really
    produces (spec.json, the three lane .md files, environment.txt, a fake .glb, the
    walk-cycle .html, the guide .html) into the cache dir it's given, so this test
    proves the sync step copies everything without needing a real swarm build."""
    store = _use_local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(upload_build, "rig_from_image", lambda doodle: {"parts": ["ok"]})
    monkeypatch.setattr(upload_build, "validate", lambda spec: [])

    written = {}

    def _fake_run(stem, doodle, rig, cache):
        for name, content in {
            f"{stem}.spec.json": b'{"name": "Test Blob"}',
            f"{stem}.biologist.md": b"# bio",
            f"{stem}.habitat.md": b"# habitat",
            f"{stem}.society.md": b"# society",
            f"{stem}.environment.txt": b"meadow",
            f"{stem}.glb": b"fake-glb-bytes",
            f"{stem}.html": b"<html>walk cycle</html>",
            f"{stem}.guide.html": b"<html>guide</html>",
        }.items():
            (cache / name).write_bytes(content)
            written[name] = content
        return cache / f"{stem}.guide.html"

    monkeypatch.setattr(upload_build, "run", _fake_run)

    result = upload_build.build_from_upload(b"real-looking-bytes", ".webp")

    assert result.refused is None
    for name, content in written.items():
        assert store.read_bytes(name) == content, f"{name} wasn't synced correctly"
    # The doodle itself and the rig must also have made it into storage — anything
    # /thumb, /anim, /guide would need to read back later.
    assert store.read_bytes(f"{result.id}.webp") == b"real-looking-bytes"
    assert store.read_bytes(f"{result.id}.rig.json") is not None


def test_each_upload_gets_a_fresh_unique_id(monkeypatch, tmp_path):
    _use_local_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(
        upload_build, "rig_from_image", lambda doodle: {"refuse": True, "refuse_reason": "x"}
    )
    monkeypatch.setattr(upload_build, "run", lambda *a, **k: None)

    a = upload_build.build_from_upload(b"one", ".png")
    b = upload_build.build_from_upload(b"two", ".png")
    assert a.id != b.id
