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
import re
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


def thumb(src: Path) -> bytes:
    """The drawing as the child made it, just scaled down.

    This used to serve the alpha-keyed cutout on a transparency checkerboard, on the
    theory that the thumbnail should show what the pipeline sees. That is a debugging
    view, not a gallery: the keyed version is our intermediate artifact, and the thing
    worth showing is the drawing. Keying also loses the paper, the crayon texture around
    the edges, and any part of the scene we discarded, all of which is the child's work.

    The keyed cutout is still what gets animated; it just isn't the poster frame.
    """
    out = CACHE / f"{src.stem}.thumb.png"
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        img = Image.open(src)
        img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        img.thumbnail((560, 560), Image.LANCZOS)
        img.save(out, "PNG", optimize=True)
    return out.read_bytes()


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


# A field guide opens in its own tab with no chrome, so give it a way back to
# the gallery. Fixed-position so it's reachable no matter how long the page is.
_BACK_BAR = (
    '<a href="/" style="position:fixed;top:12px;left:12px;z-index:9999;'
    'padding:.5rem .8rem;background:#1c2c26;color:#fff;border-radius:9px;'
    'font:600 14px system-ui,-apple-system,sans-serif;text-decoration:none;'
    'box-shadow:0 4px 14px rgba(0,0,0,.25)">← Back to gallery</a>'
)

# The template titles each section with an <h2>; some specialist sections also
# emit their own top-level <h1> title, so the page shows the title twice. Drop an
# <h1> that immediately follows an <h2> (the creature-name <h1> at the top is
# preceded by <body>, not an <h2>, so it's untouched). Fixes already-cached pages.
_DUP_TITLE = re.compile(r"(<h2\b[^>]*>.*?</h2>)\s*<h1\b[^>]*>.*?</h1>",
                        re.IGNORECASE | re.DOTALL)


def _present_guide(html: str) -> str:
    """Serve-time cleanup so cached guides get the fixes without a re-run."""
    html = _DUP_TITLE.sub(r"\1", html)
    new, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + _BACK_BAR,
                     html, count=1)
    return new if n else _BACK_BAR + html


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
        return HTMLResponse(_present_guide(out.read_text()))
    if not HAVE_KEY:
        return HTMLResponse(
            "<p>No ANTHROPIC_API_KEY found, so the text lanes can't run. "
            "The walk cycle still works at <code>/anim/" + stem + "</code>.</p>",
            status_code=503,
        )
    try:
        return HTMLResponse(_present_guide(run_swarm(stem, src, rig, PREBUILT).read_text()))
    except Exception as e:  # surface the real failure; never a silent blank page
        return HTMLResponse(f"<h3>Swarm failed</h3><pre>{type(e).__name__}: {e}</pre>", status_code=500)


def _spec_name(spec: dict):
    """The specialist agent's creature name. `name` may be a string or a
    {common_name, mock_latin_binomial} object — prefer the common name."""
    n = spec.get("name")
    if isinstance(n, dict):
        return n.get("common_name") or n.get("common") or " ".join(
            str(v) for v in n.values() if v
        )
    return n


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
        # The specialist agent's spec.json is the canonical creature name; align
        # the gallery to it so the card, walk caption, and field guide all match.
        agent_spec = PREBUILT / f"{p.stem}.spec.json"
        if agent_spec.exists():
            try:
                s = json.loads(agent_spec.read_text())
                name = _spec_name(s) or name
                vibe = s.get("vibe") or vibe
            except json.JSONDecodeError:
                pass
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
