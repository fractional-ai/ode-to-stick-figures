"""Turn one uploaded drawing into a fully animated creature with a field guide.

This is the thing uploads were missing. Before this module, POST /api/upload stored
the file and ran the alpha-key sanity check, on purpose — nothing in the web app ever
authored a rig or ran the swarm for an uploaded drawing. That's a real product gap,
not an intentional constraint: uploading is supposed to produce an animated creature,
the same as any of the 13 bundled ones.

The trick that keeps this small: stage everything into a fresh, private /tmp
directory (Vercel's /tmp is writable) and call pipeline.run() completely unchanged.
run() and its cached() helper assume a real local Path and do real file-locking —
both fine here, because nothing else on earth ever touches one upload's own private
/tmp directory. There's no second writer to lock against, so the lock is a no-op, not
a liability. Reusing run() verbatim means this module carries zero swarm-logic of its
own to drift out of sync with the tested path every other creature goes through.

Once run() returns, every artifact it wrote gets copied into Storage, and the /tmp
directory is discarded. Reading a finished upload back is a separate concern — see
serve.py's find()/rig_for(), which check Storage in addition to the bundled RIGS/
PREBUILT directories.
"""

from __future__ import annotations

import json
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "walk-cycle-anim"
UI = REPO / "ui"

for p in (REPO, SKILL, UI):
    sys.path.insert(0, str(p))

from pipeline import run  # noqa: E402
from rig_from_image import rig_from_image, validate  # noqa: E402
from storage import Storage, default_storage  # noqa: E402


@dataclass
class UploadResult:
    """What happened to one upload. `refused` is set instead of raising — a refusal
    (the drawing has no animal in it, or the rig came back invalid) is a real answer,
    not an error; see the same design already in serve.py's refusal()."""

    id: str
    refused: str | None = None


def build_from_upload(raw: bytes, suffix: str) -> UploadResult:
    """Author a rig for `raw` (an uploaded image's bytes) and, if it isn't refused,
    build the whole creature: Spec, three text lanes, GLB, walk cycle, field guide.

    `suffix` is the file extension to stage the bytes under (".jpg", ".png", ...) —
    rig_from_image() needs a real file to open, and the suffix is how PIL/the vision
    pass know what they're looking at.
    """
    upload_id = uuid.uuid4().hex[:12]
    storage = default_storage(UI / "uploads")

    # tempfile.TemporaryDirectory removes tmp_dir on exit, including on an exception —
    # nothing here needs to clean it up by hand.
    with tempfile.TemporaryDirectory(prefix=f"upload-{upload_id}-") as tmp:
        tmp_dir = Path(tmp)
        doodle = tmp_dir / f"{upload_id}{suffix}"
        doodle.write_bytes(raw)

        spec = rig_from_image(doodle)
        rig_path = tmp_dir / f"{upload_id}.rig.json"

        if spec.get("refuse"):
            rig_path.write_text(json.dumps(spec, indent=2))
            _sync_dir(tmp_dir, storage)
            return UploadResult(
                id=upload_id, refused=str(spec.get("refuse_reason") or "not animatable")
            )

        problems = validate(spec)
        if problems:
            # Not the same as a refusal (the model didn't decline; its answer just
            # doesn't satisfy the rig contract) but the user-facing outcome is the
            # same: no animation, with an honest reason instead of a crash.
            return UploadResult(id=upload_id, refused=f"couldn't build a rig: {problems[0]}")

        rig_path.write_text(json.dumps(spec, indent=2))

        # Unchanged pipeline.run(): Interpreter -> 3 parallel text lanes ->
        # environment choice -> GLB -> walk cycle -> field guide, all written into
        # tmp_dir exactly as it would write into PREBUILT for a bundled creature.
        run(upload_id, doodle, rig_path, tmp_dir)

        _sync_dir(tmp_dir, storage)
        return UploadResult(id=upload_id)


def _sync_dir(tmp_dir: Path, storage: Storage) -> None:
    """Copy every file run() (and this module) wrote into `tmp_dir` up to Storage.

    cached()'s own .lock/.tmp siblings are already gone by the time run() returns —
    it unlinks the lock in a finally and renames its tmp file onto the real one — so
    there's nothing to filter out here.
    """
    for artifact in tmp_dir.iterdir():
        storage.write_bytes(artifact.name, artifact.read_bytes())
