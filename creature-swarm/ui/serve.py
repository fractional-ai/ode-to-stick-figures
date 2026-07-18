#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "fastapi", "uvicorn", "python-multipart",
#   "pillow", "numpy", "scipy", "anthropic", "python-dotenv", "markdown", "trimesh",
# ]
# ///
"""Creature gallery — browse the drawings we can animate, drop in new ones.

Demo-grade on purpose. The filesystem IS the database:

    examples/drawings/           the drawings
    .../walk-cycle-anim/rigs/    <stem>.rig.json  -> this drawing is riggable
    creature-swarm/ui/uploads/   dropped images + their rigs
    creature-swarm/ui/.cache/    built animations and thumbnails

A drawing is "animated" iff a rig exists for its stem. No state anywhere else,
nothing to migrate, and `rm -rf .cache` is a full reset.

    ./serve.py            # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "creature-swarm" / "skills" / "walk-cycle-anim"
DRAWINGS = REPO / "examples" / "drawings"
RIGS = SKILL / "rigs"
UI = REPO / "creature-swarm" / "ui"
UPLOADS = UI / "uploads"
# Checked in: the model-derived artifacts (Creature Spec, each text lane's markdown)
# and the built walk cycles. They're small, deterministic to serve, and they cost real
# API calls to produce — so the gallery is all cache hits on a fresh clone and nobody
# has to prewarm (or pay) to demo. Regenerate any of it by deleting the file.
PREBUILT = UI / "prebuilt"
# Derived and disposable: thumbnails and assembled guides, both rebuildable offline
# from PREBUILT with no API calls.
CACHE = UI / ".cache"

sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(UI))
from build_walk_cycle import build, key  # noqa: E402
from pipeline import load_env  # noqa: E402
from pipeline import run as run_swarm  # noqa: E402

UPLOADS.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)
PREBUILT.mkdir(parents=True, exist_ok=True)
HAVE_KEY = load_env()

IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".gif"}
app = FastAPI()


def sources() -> list[Path]:
    """Every drawing we know about: shipped fixtures plus anything dropped in."""
    out = []
    for d in (DRAWINGS, UPLOADS):
        if d.is_dir():
            out += sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT)
    return out


def rig_for(stem: str) -> Path | None:
    for cand in (RIGS / f"{stem}.rig.json", UPLOADS / f"{stem}.rig.json"):
        if cand.is_file():
            return cand
    return None


def find(stem: str) -> Path | None:
    return next((p for p in sources() if p.stem == stem), None)


def figures_for(stem: str) -> int:
    """How many separate figures this drawing's rig expects to keep."""
    rig = rig_for(stem)
    if not rig:
        return 1
    try:
        return max(1, int(json.loads(rig.read_text()).get("figures", 1)))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 1


def thumb(src: Path) -> bytes:
    """Keyed cutout on transparency: shows what the pipeline actually sees.

    Honour the rig's `figures`, exactly as build() does. Keying with the default keep=1
    while the animation keeps 2 made the card lie: poptart-and-person showed a lone
    pop-tart on the card and a pop-tart plus its escort in the animation. The thumbnail's
    whole job is to preview the animation.
    """
    out = CACHE / f"{src.stem}.thumb.png"
    rig = rig_for(src.stem)
    newest = max([src.stat().st_mtime] + ([rig.stat().st_mtime] if rig else []))
    if not out.exists() or out.stat().st_mtime < newest:
        keyed, _ = key(Image.open(src), keep=figures_for(src.stem))
        keyed.thumbnail((420, 420), Image.LANCZOS)
        keyed.save(out, "PNG", optimize=True)
    return out.read_bytes()


def animation(stem: str) -> str | None:
    src, rig = find(stem), rig_for(stem)
    if not src or not rig:
        return None
    out = PREBUILT / f"{stem}.html"
    stale = not out.exists() or out.stat().st_mtime < max(
        src.stat().st_mtime, rig.stat().st_mtime, (SKILL / "template.html").stat().st_mtime
    )
    if stale:
        build(src, rig, out)
    return out.read_text()


@app.get("/thumb/{stem}")
def get_thumb(stem: str):
    src = find(stem)
    if not src:
        return Response(status_code=404)
    return Response(thumb(src), media_type="image/png")


@app.get("/raw/{stem}")
def get_raw(stem: str):
    src = find(stem)
    if not src:
        return Response(status_code=404)
    return Response(src.read_bytes(), media_type="image/*")


@app.get("/anim/{stem}", response_class=HTMLResponse)
def get_anim(stem: str):
    html = animation(stem)
    if html is None:
        return HTMLResponse("<p>No rig for this drawing yet.</p>", status_code=404)
    return HTMLResponse(html)


def refusal(spec: dict) -> str | None:
    """Is this rig a negative fixture — a drawing we should decline to animate?

    Some rigs exist to document a refusal (snowmen-scene: a painted scene with no
    animal in it). A rig file is otherwise our only signal for "animated", so
    without this check the gallery advertises those as animated and someone clicks
    through to paper slabs sliding sideways. An honest "won't animate, here's why"
    is a feature; silent plausible garbage is the worst thing we can demo.
    """
    if spec.get("refuse"):
        return str(spec.get("refuse_reason") or spec.get("vibe") or "not animatable")
    if "NEGATIVE fixture" in spec.get("_comment", ""):
        return spec.get("vibe") or "documented as not animatable"
    return None


@app.get("/guide/{stem}", response_class=HTMLResponse)
def get_guide(stem: str):
    """The full field guide: Interpreter -> 3 text lanes + Animator -> assembled page.

    Cached to disk after the first run — the swarm is a few seconds of model calls and
    a demo shouldn't pay that twice.
    """
    src, rig = find(stem), rig_for(stem)
    if not src or not rig:
        return HTMLResponse("<p>No rig for this drawing yet.</p>", status_code=404)
    out = PREBUILT / f"{stem}.guide.html"
    if out.exists():
        return HTMLResponse(out.read_text())
    if not HAVE_KEY:
        return HTMLResponse(
            "<p>No ANTHROPIC_API_KEY found, so the text lanes can't run. "
            "The walk cycle still works at <code>/anim/" + stem + "</code>.</p>",
            status_code=503,
        )
    try:
        return HTMLResponse(run_swarm(stem, src, rig, PREBUILT).read_text())
    except Exception as e:  # surface the real failure; never a silent blank page
        return HTMLResponse(f"<h3>Swarm failed</h3><pre>{type(e).__name__}: {e}</pre>", status_code=500)


@app.get("/api/creatures")
def api_creatures():
    items = []
    for p in sources():
        rig = rig_for(p.stem)
        name, vibe, why = p.stem.replace("-", " "), "", None
        if rig:
            try:
                spec = json.loads(rig.read_text())
                name = spec.get("name") or name
                vibe = spec.get("vibe") or ""
                why = refusal(spec)
            except json.JSONDecodeError:
                why = "rig file is not valid JSON"
        items.append(
            {
                "stem": p.stem,
                "name": name,
                "vibe": vibe,
                "animated": rig is not None and why is None,
                "refused": why,
                "uploaded": p.parent == UPLOADS,
            }
        )
    items.sort(key=lambda i: (not i["animated"], bool(i["refused"]), i["stem"]))
    return items


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """Accept a dropped drawing, key it, and report what we can and can't do.

    We deliberately do NOT claim to animate it. Keying is deterministic and runs
    here; authoring a rig (image-space polygons and pivots) needs a vision pass,
    which is the one genuinely unsolved step. Saying so is better than a spinner
    that never resolves.
    """
    raw = await file.read()
    stem = Path(file.filename or "dropped").stem
    suffix = Path(file.filename or "").suffix.lower() or ".png"

    if suffix == ".heic":
        return JSONResponse(
            {"stem": stem, "error": "HEIC needs converting first (sips -s format jpeg)."},
            status_code=415,
        )
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:
        return JSONResponse({"stem": stem, "error": "Not a readable image."}, status_code=415)

    dest = UPLOADS / f"{stem}{suffix}"
    n = 1
    while dest.exists():
        dest = UPLOADS / f"{stem}-{n}{suffix}"
        n += 1
    dest.write_bytes(raw)

    keyed, stats = key(Image.open(dest))
    warn = None
    if stats["blobs"] >= 3 and stats["dominance"] < 0.80:
        warn = (
            f"{stats['blobs']} comparable blobs (dominance {stats['dominance']:.2f}) — "
            "either several figures, or no single creature to animate."
        )
    return {
        "stem": dest.stem,
        "animated": rig_for(dest.stem) is not None,
        "stats": {k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()},
        "warning": warn,
        "needs_rig": True,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((UI / "index.html").read_text())


if __name__ == "__main__":
    import uvicorn

    print("gallery: http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
