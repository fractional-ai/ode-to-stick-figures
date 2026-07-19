#!/usr/bin/env -S uv run --quiet
"""Rig every drawing that lacks one, then build every field guide. Idempotent.

The gallery is only as good as its rig coverage: a drawing with no rig reads "needs a
rig" and can't be demoed. This authors the missing rigs with the vision pass and warms
every guide, so the demo is all cache hits and nothing runs the swarm live in a room.

Everything is cached per API result, so re-running costs nothing for work already done.

    ./prewarm.py            # all drawings
    ./prewarm.py shark-dog bee
"""

from __future__ import annotations

import json
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

UI = Path(__file__).resolve().parent
REPO = UI.parents[0]
SKILL = REPO / "skills" / "walk-cycle-anim"
RIGS = SKILL / "rigs"
DRAWINGS = REPO / "examples" / "drawings"
CACHE = UI / "prebuilt"  # committed: model-derived artifacts + built walk cycles

for p in (UI, SKILL, REPO):
    sys.path.insert(0, str(p))

from pipeline import load_env, run  # noqa: E402

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def drawings() -> list[Path]:
    want = set(sys.argv[1:])
    out = [p for p in sorted(DRAWINGS.iterdir()) if p.suffix.lower() in IMG_EXT]
    return [p for p in out if not want or p.stem in want]


def ensure_rig(src: Path) -> tuple[str, str]:
    """Author a rig if missing. Returns (stem, status)."""
    rig = RIGS / f"{src.stem}.rig.json"
    if rig.exists():
        return src.stem, "rig: cached"
    from rig_from_image import rig_from_image, validate

    spec = rig_from_image(src)
    if spec.get("refuse"):
        # A refusal is a real answer. Persist it so the gallery shows "won't animate"
        # with the reason instead of silently re-asking the model on every visit.
        rig.write_text(json.dumps(spec, indent=2))
        return src.stem, f"rig: REFUSED — {spec.get('refuse_reason')}"
    problems = validate(spec)
    if problems:
        return src.stem, f"rig: INVALID — {problems[0]}"
    rig.write_text(json.dumps(spec, indent=2))
    return (
        src.stem,
        f"rig: authored ({len(spec.get('parts', []))} parts, faces={spec.get('faces')})",
    )


def ensure_guide(src: Path) -> str:
    rig = RIGS / f"{src.stem}.rig.json"
    if not rig.exists():
        return "guide: skipped (no rig)"
    spec = json.loads(rig.read_text())
    if spec.get("refuse") or "NEGATIVE fixture" in spec.get("_comment", ""):
        return "guide: skipped (refused drawing)"
    if (CACHE / f"{src.stem}.guide.html").exists():
        return "guide: cached"
    run(src.stem, src, rig, CACHE)
    return "guide: built"


def one(src: Path) -> str:
    try:
        _, rig_status = ensure_rig(src)
        return f"{src.stem:26} {rig_status:52} {ensure_guide(src)}"
    except Exception as e:  # noqa: BLE001 — one drawing failing must not abort the batch
        return f"{src.stem:26} FAILED: {type(e).__name__}: {str(e)[:90]}"


def main() -> None:
    if not load_env():
        raise SystemExit("No ANTHROPIC_API_KEY found in any .env up the tree.")
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = drawings()
    print(f"prewarming {len(todo)} drawings…\n", flush=True)
    # Bounded but real concurrency: these are long provider calls and our limits are
    # nowhere near the constraint. Serialising this would take minutes we don't have.
    with ThreadPoolExecutor(max_workers=12) as pool:
        for fut in as_completed([pool.submit(one, p) for p in todo]):
            print(fut.result(), flush=True)
    print("\ndone.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
