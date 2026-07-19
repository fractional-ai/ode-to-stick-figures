#!/usr/bin/env -S uv run --quiet
"""Creature gallery — browse the drawings we can animate, drop in new ones.

Demo-grade on purpose. The filesystem IS the database, locally:

    examples/drawings/           the drawings
    .../walk-cycle-anim/rigs/    <stem>.rig.json  -> this drawing is riggable
    ui/uploads/                  dropped images + their rigs

A drawing is "animated" iff a rig exists for its stem. No state anywhere else,
nothing to migrate, and `rm -rf ui/uploads` is a full reset.

Deployed on Vercel, none of the directories above are writable — the filesystem is
read-only outside of /tmp. Nothing here creates a directory at import time for
exactly that reason: a module-load-time mkdir() against a path that doesn't exist
in the deploy bundle would crash every cold start, before any route even ran.

    ./serve.py            # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import html as html_mod  # aliased: `html` is a local variable in the route handlers
import io
import json
import os
import re
import sys
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "walk-cycle-anim"
DRAWINGS = REPO / "examples" / "drawings"
RIGS = SKILL / "rigs"
UI = REPO / "ui"
UPLOADS = UI / "uploads"
# Checked in: the model-derived artifacts (Creature Spec, each text lane's markdown)
# and the built walk cycles. They're small, deterministic to serve, and they cost real
# API calls to produce — so the gallery is all cache hits on a fresh clone and nobody
# has to prewarm (or pay) to demo. Regenerate any of it by deleting the file. Always
# exists already (bundled, committed) — never created here.
PREBUILT = UI / "prebuilt"

sys.path.insert(0, str(SKILL))
sys.path.insert(0, str(UI))
from build_walk_cycle import build, key  # noqa: E402
from pipeline import IMG_EXT, anim_overrides, load_env, normalize_spec  # noqa: E402
from pipeline import run as run_swarm  # noqa: E402

HAVE_KEY = load_env()
# Real, documented Vercel system env var, populated at runtime once "Access to System
# Environment Variables" is enabled in Project Settings. Gates the two places that used
# to rebuild-and-write a bundled creature's PREBUILT artifacts on a cache miss
# (animation()'s staleness rebuild, get_guide()'s run_swarm() call) — both attempt a
# filesystem write, and Vercel's filesystem is read-only outside /tmp. The bundled 13
# creatures are meant to always be prewarmed before a deploy; a miss there is a real gap
# (a missing prewarm, a stale build) that should surface as "not available", not as a
# crash. Locally this is always False, so nothing here changes local dev behavior.
ON_VERCEL = os.environ.get("VERCEL") == "1"

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

    Computed fresh on every request rather than cached to disk. A PIL resize on an
    image this size costs low-single-digit milliseconds — cheap enough that a
    persistent cache bought nothing but a write path, and Vercel's filesystem is
    read-only outside /tmp, so that write path would need its own storage backend for
    something this cheap to not have at all.
    """
    img = Image.open(src)
    img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
    img.thumbnail((560, 560), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _spec_overrides(stem: str) -> dict | None:
    """Rebuild the Spec-derived build arguments from what the swarm already cached.

    The Spec and the chosen environment are both checked in, so we can reproduce the
    swarm's own build offline: no API key, no model calls. Returns None when there's no
    cached Spec (a freshly dropped drawing), in which case the rig's defaults are all
    we have and all we can honestly use.
    """
    spec_file = PREBUILT / f"{stem}.spec.json"
    if not spec_file.is_file():
        return None
    try:
        spec = normalize_spec(json.loads(spec_file.read_text()))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    env_file = PREBUILT / f"{stem}.environment.txt"
    env = env_file.read_text().strip() if env_file.is_file() else "meadow"
    return anim_overrides(spec, env, stem)


def animation(stem: str) -> str | None:
    """The built walk cycle for one drawing, or None if we can't animate it.

    Locally: rebuild when the drawing, the rig, or the renderer template is newer than
    what we have, so editing a rig or the template shows up on the next request instead
    of serving a stale build forever. Rebuild through the same Spec overrides the swarm
    used, or the refresh quietly downgrades the animation to the rig's raw defaults and
    it stops matching the name and world on its own field guide.

    On Vercel: never rebuild. The bundled 13 are meant to always be prewarmed before a
    deploy, and the filesystem is read-only outside /tmp — attempting the write above
    would crash the request instead of degrading it. A missing PREBUILT entry there
    means a prewarm was skipped, not a cache to fill on demand.
    """
    src, rig = find(stem), rig_for(stem)
    if not src or not rig:
        return None
    out = PREBUILT / f"{stem}.html"
    if ON_VERCEL:
        return out.read_text() if out.exists() else None
    stale = not out.exists() or out.stat().st_mtime < max(
        src.stat().st_mtime, rig.stat().st_mtime, (SKILL / "template.html").stat().st_mtime
    )
    if stale:
        overrides = _spec_overrides(stem)
        if overrides:
            build(src, rig, out, color=True, overrides=overrides)
        else:
            build(src, rig, out)
    return out.read_text()


@app.get("/thumb/{stem}")
def get_thumb(stem: str):
    src = find(stem)
    if not src:
        return Response(status_code=404)
    return Response(thumb(src), media_type="image/png")


@app.get("/anim/{stem}", response_class=HTMLResponse)
def get_anim(stem: str):
    why = refusal_for(stem)
    if why:
        return HTMLResponse(
            f"<p>We won't animate this one: {html_mod.escape(why)}</p>", status_code=422
        )
    html = animation(stem)
    if html is None:
        if ON_VERCEL and rig_for(stem) is not None:
            return HTMLResponse(
                "<p>This creature hasn't been built into this deployment yet. It "
                "needs a <code>./prewarm.py</code> run and a redeploy.</p>",
                status_code=503,
            )
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


def refusal_for(stem: str) -> str | None:
    """The refusal reason for a stem, straight from its rig, or None.

    The listing isn't the only way in. Hiding the buttons in the gallery leaves
    /anim/<stem> and /guide/<stem> reachable by URL, and those routes did the work
    anyway: hitting /guide/snowmen-scene ran the swarm on a painting of snowmen and
    invented "Segmented Bucket-Hat Wader (Segmentus caputbalneus), locomotion: float".
    That is the plausible garbage the refusal exists to prevent, and it billed real
    model calls to produce it. Enforce where the work happens, not where it's advertised.
    """
    rig = rig_for(stem)
    if not rig:
        return None
    try:
        return refusal(json.loads(rig.read_text()))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


# A field guide opens in its own tab with no chrome, so give it a way back to
# the gallery. Fixed-position so it's reachable no matter how long the page is.
_BACK_BAR = (
    '<a href="/" style="position:fixed;top:12px;left:12px;z-index:9999;'
    "padding:.5rem .8rem;background:#1c2c26;color:#fff;border-radius:9px;"
    "font:600 14px system-ui,-apple-system,sans-serif;text-decoration:none;"
    'box-shadow:0 4px 14px rgba(0,0,0,.25)">← Back to gallery</a>'
)

# The template titles each section with an <h2>; some specialist sections also
# emit their own top-level <h1> title, so the page shows the title twice. Drop an
# <h1> that immediately follows an <h2> (the creature-name <h1> at the top is
# preceded by <body>, not an <h2>, so it's untouched). Fixes already-cached pages.
_DUP_TITLE = re.compile(r"(<h2\b[^>]*>.*?</h2>)\s*<h1\b[^>]*>.*?</h1>", re.IGNORECASE | re.DOTALL)


def _present_guide(html: str) -> str:
    """Serve-time cleanup so cached guides get the fixes without a re-run."""
    html = _DUP_TITLE.sub(r"\1", html)
    new, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + _BACK_BAR, html, count=1)
    return new if n else _BACK_BAR + html


@app.get("/guide/{stem}", response_class=HTMLResponse)
def get_guide(stem: str):
    """The full field guide: Interpreter -> 3 text lanes + Animator -> assembled page.

    Cached to disk after the first run — the swarm is a few seconds of model calls and
    a demo shouldn't pay that twice. On Vercel, a cache miss never runs the swarm here
    at all (see ON_VERCEL below) — the filesystem is read-only outside /tmp, and the
    bundled 13 are meant to always be prewarmed before a deploy.
    """
    src, rig = find(stem), rig_for(stem)
    if not src or not rig:
        return HTMLResponse("<p>No rig for this drawing yet.</p>", status_code=404)
    why = refusal_for(stem)
    if why:
        # Before the cache check, and before HAVE_KEY: a refusal must never reach the
        # swarm. This route used to fabricate a creature for a drawing that has none.
        return HTMLResponse(
            f"<p>We won't write a field guide for this one: {html_mod.escape(why)}</p>",
            status_code=422,
        )
    out = PREBUILT / f"{stem}.guide.html"
    if out.exists():
        return HTMLResponse(_present_guide(out.read_text()))
    if ON_VERCEL:
        # Never attempt run_swarm() here: PREBUILT is a read-only bundle on Vercel, and
        # writing into it is exactly what run_swarm() does. A miss means a prewarm was
        # skipped, not a cache to fill on demand.
        return HTMLResponse(
            "<p>This creature's field guide hasn't been built into this deployment "
            "yet. It needs a <code>./prewarm.py</code> run and a redeploy.</p>",
            status_code=503,
        )
    if not HAVE_KEY:
        return HTMLResponse(
            "<p>No ANTHROPIC_API_KEY found, so the text lanes can't run. "
            "The walk cycle still works at <code>/anim/" + stem + "</code>.</p>",
            status_code=503,
        )
    try:
        return HTMLResponse(_present_guide(run_swarm(stem, src, rig, PREBUILT).read_text()))
    except Exception as e:  # noqa: BLE001 — surface the real failure; never a silent blank page
        detail = html_mod.escape(f"{type(e).__name__}: {e}")
        return HTMLResponse(f"<h3>Swarm failed</h3><pre>{detail}</pre>", status_code=500)


def _spec_name(spec: dict):
    """The specialist agent's creature name. `name` may be a string or a
    {common_name, mock_latin_binomial} object — prefer the common name."""
    n = spec.get("name")
    if isinstance(n, dict):
        return n.get("common_name") or n.get("common") or " ".join(str(v) for v in n.values() if v)
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
    if suffix not in IMG_EXT:
        # sources() only lists files whose suffix is in IMG_EXT, so anything else saved
        # to UPLOADS is an orphan: this would return 200 with stats, then /thumb, /anim
        # and /guide would all 404 for it and the gallery would never show it existed.
        return JSONResponse(
            {"stem": stem, "error": f"Unsupported file type {suffix!r}."}, status_code=415
        )
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:  # noqa: BLE001 — PIL raises anything at all on a malformed upload
        return JSONResponse({"stem": stem, "error": "Not a readable image."}, status_code=415)

    dest = UPLOADS / f"{stem}{suffix}"
    n = 1
    while dest.exists():
        dest = UPLOADS / f"{stem}-{n}{suffix}"
        n += 1
    dest.write_bytes(raw)

    # Only the stats matter here: this call is the alpha-key run purely to sanity-check what
    # got dropped on us. The keyed image itself is rebuilt at animation time.
    _, stats = key(Image.open(dest))
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

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"gallery: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
