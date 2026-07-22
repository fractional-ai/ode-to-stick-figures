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

import asyncio
import html as html_mod  # aliased: `html` is a local variable in the route handlers
import io
import json
import os
import re
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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
import auth  # noqa: E402
import upload_build  # noqa: E402
from build_walk_cycle import build, key  # noqa: E402
from pages import error_page  # noqa: E402
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
# Built once at import time (after load_env(), so a locally-set BLOB_READ_WRITE_TOKEN
# from .env is already in os.environ by the time this checks for it). Every uploaded
# creature's artifacts go through this, never a bare local Path — on a local dev
# clone it's a LocalStorage rooted at UPLOADS (so it happens to be the same directory
# sources() already scans); on Vercel it's Blob storage, where nothing is local at all.
UPLOAD_STORAGE = upload_build.default_storage(UPLOADS)

app = FastAPI()
# No-op unless GOOGLE_CLIENT_ID/SECRET are set (see auth.py) — gates only
# POST /api/upload, via Depends(auth.require_upload_auth) below. Every other route,
# including browsing anything an already-uploaded creature produced, stays public.
auth.install(app)


def sources() -> list[Path]:
    """Every LOCAL drawing we know about: shipped fixtures, plus anything dropped in
    on a dev clone (where an upload's doodle happens to land in this same directory).
    Does not see a Blob-only upload — see _uploaded_stems() for that."""
    out = []
    for d in (DRAWINGS, UPLOADS):
        if d.is_dir():
            out += sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT)
    return out


def _uploaded_stems() -> list[str]:
    """Every uploaded creature's stem, from Storage. On a dev clone this overlaps
    with what sources() already finds locally (deduplicated by the caller) — on
    Vercel it's the only way to discover an uploaded creature at all, since nothing
    about Blob storage is a local directory sources() could scan.

    Path(k).stem would be wrong here: ".rig.json" is two suffixes, so Path("x.rig.json").stem
    is "x.rig", not "x" — strip the known literal suffix instead of asking Path to guess.
    """
    return sorted(
        k.removesuffix(".rig.json") for k in UPLOAD_STORAGE.list_keys() if k.endswith(".rig.json")
    )


def rig_for(stem: str) -> Path | None:
    """A BUNDLED creature's rig, as a local Path. None for anything else, including
    an uploaded creature — its rig lives in Storage; see rig_bytes_for()."""
    cand = RIGS / f"{stem}.rig.json"
    return cand if cand.is_file() else None


def rig_bytes_for(stem: str) -> bytes | None:
    """This stem's rig, wherever it actually is: the bundled RIGS directory first,
    then Storage. Storage is checked either way — on a dev clone that's a second,
    redundant look at the same file rig_for() already found locally, which is cheap
    and correct; it's the only path that resolves at all when Storage is Blob-backed."""
    local = rig_for(stem)
    if local:
        return local.read_bytes()
    return UPLOAD_STORAGE.read_bytes(f"{stem}.rig.json")


def drawing_bytes_for(stem: str) -> bytes | None:
    """This stem's source drawing, wherever it actually is. Bundled and dev-clone
    uploads already have a local Path via find(); a Blob-only upload doesn't, so this
    falls back to listing Storage for the one key matching stem + a known image
    extension (Storage has no "get me the file with this stem, whatever its
    extension" lookup, only exact keys)."""
    src = find(stem)
    if src:
        return src.read_bytes()
    for k in UPLOAD_STORAGE.list_keys(prefix=f"{stem}."):
        if Path(k).suffix.lower() in IMG_EXT:
            return UPLOAD_STORAGE.read_bytes(k)
    return None


def _artifact(filename: str) -> bytes | None:
    """One build artifact (spec.json, environment.txt, the walk-cycle html, the
    guide html) — bundled PREBUILT first, then Storage. `filename` is the full name,
    e.g. f"{stem}.spec.json"."""
    local = PREBUILT / filename
    if local.is_file():
        return local.read_bytes()
    return UPLOAD_STORAGE.read_bytes(filename)


def find(stem: str) -> Path | None:
    return next((p for p in sources() if p.stem == stem), None)


def thumb(raw: bytes) -> bytes:
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

    Takes bytes rather than a Path so it works the same whether the source is a
    bundled local file or an uploaded creature's drawing fetched from Storage — see
    drawing_bytes_for(), which resolves either case before calling this.
    """
    img = Image.open(io.BytesIO(raw))
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

    An uploaded creature (rig_for() returns None — it isn't in the bundled RIGS
    directory) was already built once, synchronously, at upload time. There's
    nothing to rebuild here: either its walk cycle is already in Storage, or the
    build is still running, failed, or the stem doesn't exist at all.
    """
    rig = rig_for(stem)
    if rig is None:
        raw = UPLOAD_STORAGE.read_bytes(f"{stem}.html")
        return raw.decode() if raw is not None else None
    src = find(stem)
    if not src:
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
    raw = drawing_bytes_for(stem)
    if raw is None:
        return Response(status_code=404)
    return Response(thumb(raw), media_type="image/png")


@app.get("/anim/{stem}", response_class=HTMLResponse)
def get_anim(stem: str):
    why = refusal_for(stem)
    if why:
        return error_page(
            status=422,
            code="A considered call",
            heading="We won't animate this one",
            body=f"<p>{html_mod.escape(why)}</p>",
        )
    html = animation(stem)
    if html is None:
        if ON_VERCEL and rig_for(stem) is not None:
            return error_page(
                status=503,
                heading="Not built into this deployment yet",
                body="<p>This creature needs a <code>./prewarm.py</code> run and a redeploy.</p>",
            )
        if rig_bytes_for(stem) is not None:
            # A rig exists (an upload, since a bundled miss was just handled above)
            # but nothing built yet — the build is still running, failed partway, or
            # a concurrent request is mid-build. Distinct from "no rig at all."
            return error_page(
                status=503,
                heading="Still being built",
                body="<p>This creature is still being built, or the build didn't finish. "
                "Try again in a moment.</p>",
            )
        return error_page(
            status=404,
            heading="No rig for this drawing yet",
            body="<p>There's nothing to animate here — this drawing has no rig.</p>",
        )
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
    raw = rig_bytes_for(stem)
    if raw is None:
        return None
    try:
        return refusal(json.loads(raw))
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
# emit their own heading right after it, so the page shows the title twice. Match a
# section <h2> followed by an <h1>-<h3>, and drop the second only when its text
# repeats the section title — identical ("Habitat & Ecology" / "Habitat & Ecology")
# or the title as a prefix ("Folklore & Society" / "Folklore & Society: ..."). A
# genuinely different subhead ("Folk Traditions of the ... Peoples") is left alone.
# The creature-name <h1> at the top follows <body>, not an <h2>, so it's untouched.
# Fixes already-cached pages. [^<]* keeps each heading's text from spanning markup.
_DUP_TITLE = re.compile(
    r"(<h2\b[^>]*>([^<]*)</h2>)\s*<h(?P<lvl>[1-3])\b[^>]*>(?P<txt>[^<]*)</h(?P=lvl)>",
    re.IGNORECASE,
)


def _norm_heading(text: str) -> str:
    """Lower-case, alphanumerics only — a lenient compare that ignores case,
    whitespace, punctuation, and entity spelling (&amp; vs &)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _dedup_heading(m: re.Match[str]) -> str:
    section, following = _norm_heading(m.group(2)), _norm_heading(m.group("txt"))
    if section and (following == section or following.startswith(section)):
        return m.group(1)  # drop the repeated heading, keep the section <h2>
    return m.group(0)  # a different subhead — leave both


def _present_guide_body(html: str) -> str:
    """Serve-time cleanup so cached guides get the fixes without a re-run. No back bar:
    inside the sandboxed frame that link would navigate the frame, not the tab, so the
    wrapper page owns it instead."""
    return _DUP_TITLE.sub(_dedup_heading, html)


def _present_guide(html: str) -> str:
    """Cleanup plus the back bar, for guides served as the top-level document."""
    html = _present_guide_body(html)
    new, n = re.subn(r"(<body[^>]*>)", lambda m: m.group(1) + _BACK_BAR, html, count=1)
    return new if n else _BACK_BAR + html


# An uploaded guide is model-written prose assembled from a drawing that a signed-in
# uploader chose, and nothing in the render path strips HTML — so serving one as
# first-party content lets an uploader persist script that runs for every visitor,
# with the gallery's own origin and cookies.
#
# Sanitizing was the other option and it doesn't work here: guides carry an inline
# <script> that drives the walk-cycle canvas plus an external model-viewer import, so
# an allowlist strict enough to be safe would break every uploaded guide's animation.
#
# A sandboxed iframe keeps the animation and still contains it. `allow-scripts` WITHOUT
# `allow-same-origin` is the whole trick: script runs, but in an opaque origin, so it
# can't read the session cookie, touch the parent DOM, or call our API as the viewer.
# Bundled guides are repo-authored and skip all of this.
_GUIDE_SANDBOX = "allow-scripts allow-popups"


def _sandboxed_guide_page(stem: str) -> str:
    """The wrapper the browser actually loads: our chrome, guide in a sandboxed frame."""
    src = f"/guide/{html_mod.escape(stem, quote=True)}/raw"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Field guide</title>"
        "<style>html,body{margin:0;height:100%}iframe{border:0;width:100%;height:100%;"
        "display:block}</style></head><body>"
        f"{_BACK_BAR}"
        f"<iframe sandbox=\"{_GUIDE_SANDBOX}\" src='{src}' title='Field guide'></iframe>"
        "</body></html>"
    )


@app.get("/guide/{stem}", response_class=HTMLResponse)
def get_guide(stem: str):
    """The full field guide: Interpreter -> 3 text lanes + Animator -> assembled page.

    Cached to disk after the first run — the swarm is a few seconds of model calls and
    a demo shouldn't pay that twice. On Vercel, a cache miss never runs the swarm here
    at all (see ON_VERCEL below) — the filesystem is read-only outside /tmp, and the
    bundled 13 are meant to always be prewarmed before a deploy.

    An uploaded creature (rig is None below — not in the bundled RIGS directory) was
    already built once, synchronously, at upload time (see upload_build.py). This
    route never runs the swarm for one; it only ever reads back what's already in
    Storage.
    """
    rig = rig_for(stem)
    if rig is None:
        raw_rig = UPLOAD_STORAGE.read_bytes(f"{stem}.rig.json")
        if raw_rig is None:
            return error_page(
                status=404,
                heading="No rig for this drawing yet",
                body="<p>There's nothing to write up here — this drawing has no rig.</p>",
            )
        why = refusal_for(stem)
        if why:
            return error_page(
                status=422,
                code="A considered call",
                heading="We won't write a field guide for this one",
                body=f"<p>{html_mod.escape(why)}</p>",
            )
        if not UPLOAD_STORAGE.exists(f"{stem}.guide.html"):
            return error_page(
                status=503,
                heading="Still being built",
                body="<p>This creature is still being built, or the build didn't finish. "
                "Try again in a moment.</p>",
            )
        # Never the guide's own HTML at this URL — see _sandboxed_guide_page.
        return HTMLResponse(_sandboxed_guide_page(stem))

    src = find(stem)
    if not src:
        return error_page(
            status=404,
            heading="No rig for this drawing yet",
            body="<p>There's nothing to write up here — this drawing has no rig.</p>",
        )
    why = refusal_for(stem)
    if why:
        # Before the cache check, and before HAVE_KEY: a refusal must never reach the
        # swarm. This route used to fabricate a creature for a drawing that has none.
        return error_page(
            status=422,
            code="A considered call",
            heading="We won't write a field guide for this one",
            body=f"<p>{html_mod.escape(why)}</p>",
        )
    out = PREBUILT / f"{stem}.guide.html"
    if out.exists():
        return HTMLResponse(_present_guide(out.read_text()))
    if ON_VERCEL:
        # Never attempt run_swarm() here: PREBUILT is a read-only bundle on Vercel, and
        # writing into it is exactly what run_swarm() does. A miss means a prewarm was
        # skipped, not a cache to fill on demand.
        return error_page(
            status=503,
            heading="Not built into this deployment yet",
            body="<p>This creature's field guide needs a <code>./prewarm.py</code> run "
            "and a redeploy.</p>",
        )
    if not HAVE_KEY:
        return error_page(
            status=503,
            heading="Text lanes unavailable",
            body="<p>No <code>ANTHROPIC_API_KEY</code> found, so the text lanes can't run. "
            f"The walk cycle still works at <code>/anim/{html_mod.escape(stem)}</code>.</p>",
        )
    try:
        return HTMLResponse(_present_guide(run_swarm(stem, src, rig, PREBUILT).read_text()))
    except Exception as e:  # noqa: BLE001 — surface the real failure; never a silent blank page
        detail = html_mod.escape(f"{type(e).__name__}: {e}")
        return HTMLResponse(f"<h3>Swarm failed</h3><pre>{detail}</pre>", status_code=500)


@app.get("/guide/{stem}/raw", response_class=HTMLResponse)
def get_guide_raw(stem: str):
    """The uploaded guide's own HTML, for the sandboxed iframe in /guide/{stem}.

    Uploaded creatures only — a bundled stem 404s here, since bundled guides are served
    directly and have no reason to exist at this URL.

    The CSP `sandbox` directive repeats the iframe's sandbox attribute as a response
    header so the isolation holds even when this URL is opened directly, which a
    determined attacker would obviously try rather than politely staying in the frame.
    """
    if rig_for(stem) is not None:
        raise HTTPException(status_code=404, detail="Not an uploaded creature.")
    raw_guide = UPLOAD_STORAGE.read_bytes(f"{stem}.guide.html")
    if raw_guide is None:
        raise HTTPException(status_code=404, detail="No guide for this creature.")
    return HTMLResponse(
        _present_guide_body(raw_guide.decode()),
        headers={"Content-Security-Policy": f"sandbox {_GUIDE_SANDBOX}"},
    )


def _spec_name(spec: dict):
    """The specialist agent's creature name. `name` may be a string or a
    {common_name, mock_latin_binomial} object — prefer the common name."""
    n = spec.get("name")
    if isinstance(n, dict):
        return n.get("common_name") or n.get("common") or " ".join(str(v) for v in n.values() if v)
    return n


@app.get("/api/creatures")
def api_creatures():
    # Local Paths (bundled + dev-clone uploads) union Storage-only stems (Blob
    # uploads, invisible to sources() since none of Blob storage is a local
    # directory). dict.setdefault so a dev-clone upload found by both isn't listed
    # twice — sources() gives it a real Path (used only for the "uploaded" flag
    # below); a Blob-only upload has none.
    stems: dict[str, Path | None] = {p.stem: p for p in sources()}
    for stem in _uploaded_stems():
        stems.setdefault(stem, None)

    items = []
    for stem, p in stems.items():
        raw_rig = rig_bytes_for(stem)
        name, vibe, why = stem.replace("-", " "), "", None
        w = h = None
        if raw_rig is not None:
            try:
                spec = json.loads(raw_rig)
                name = spec.get("name") or name
                vibe = spec.get("vibe") or ""
                why = refusal(spec)
                # The rig records the source drawing's pixel size; hand it to the card so
                # the plate reserves the right box before the thumb loads (see #69). The
                # thumbnail keeps this aspect ratio, so w/h double as the img's.
                img = spec.get("image")
                if isinstance(img, dict):
                    w, h = img.get("w"), img.get("h")
            except json.JSONDecodeError:
                why = "rig file is not valid JSON"
        # The specialist agent's spec.json is the canonical creature name; align
        # the gallery to it so the card, walk caption, and field guide all match.
        agent_spec_raw = _artifact(f"{stem}.spec.json")
        if agent_spec_raw is not None:
            try:
                s = json.loads(agent_spec_raw)
                name = _spec_name(s) or name
                vibe = s.get("vibe") or vibe
            except json.JSONDecodeError:
                pass
        items.append(
            {
                "stem": stem,
                "name": name,
                "vibe": vibe,
                # For an uploaded creature the rig alone isn't enough: /anim reads the
                # stored walk cycle and never rebuilds one, so a rig-only stem (partial
                # Blob sync, or a build that died after the rig) would advertise live
                # walk/guide controls that both 503. Bundled stems keep the old test —
                # their artifacts ship in the bundle alongside the rig.
                "animated": raw_rig is not None
                and why is None
                and (p is not None or UPLOAD_STORAGE.exists(f"{stem}.html")),
                "refused": why,
                "uploaded": p is None or p.parent == UPLOADS,
                # Source drawing dimensions when the rig recorded them, else null. The
                # card sets them on the <img> so the grid reserves space and stops
                # reflowing as thumbs arrive (#69).
                "w": w,
                "h": h,
            }
        )
    items.sort(key=lambda i: (not i["animated"], bool(i["refused"]), i["stem"]))
    return items


@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(...), _user: dict | None = Depends(auth.require_upload_auth)
):
    """Accept a dropped drawing and build it into a real animated creature.

    Gated on a real Google Workspace account when auth is configured (see auth.py) —
    everything else in this file stays public. `_user` isn't used for anything beyond
    the dependency's own 401 on an unauthenticated request; there's no per-user state.

    This used to stop after storing the file and running the alpha-key sanity check —
    deliberately: authoring a rig needs a vision pass, and a spinner that never
    resolves is worse than an honest "we can't animate this yet." That's no longer
    the right call to make. Upload is supposed to produce an animated creature with a
    field guide, the same as any of the 13 bundled ones — see upload_build.py, which
    does the actual rig-authoring + swarm run.

    The build takes on the order of a minute (measured: ~51s for a real drawing, rig
    authoring plus the full swarm, no retries). Runs in a thread so it doesn't block
    the event loop for the whole request — a plain blocking call here would stall
    every other concurrent request against this same server for as long as this one
    upload takes to build.
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
        return JSONResponse(
            {"stem": stem, "error": f"Unsupported file type {suffix!r}."}, status_code=415
        )
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception:  # noqa: BLE001 — PIL raises anything at all on a malformed upload
        return JSONResponse({"stem": stem, "error": "Not a readable image."}, status_code=415)

    # Before the build, not during it: rig_from_image() reads os.environ["ANTHROPIC_API_KEY"]
    # directly, so without a key the whole upload died as a KeyError-shaped 500 a minute
    # in. The read-only routes already gate on HAVE_KEY; this one has more reason to,
    # since it's the expensive path.
    if not HAVE_KEY:
        return JSONResponse(
            {
                "stem": stem,
                "error": "No ANTHROPIC_API_KEY on this deployment, so a drawing can't "
                "be built into a creature. Browsing still works.",
            },
            status_code=503,
        )

    # A fast, free, heuristic pre-flight signal, independent of the real (much
    # smarter) refusal the vision pass below can make. Kept because it's informative
    # before spending a model call: multiple comparable blobs usually means several
    # figures or no single clear subject.
    _, stats = key(img)
    warn = None
    if stats["blobs"] >= 3 and stats["dominance"] < 0.80:
        warn = (
            f"{stats['blobs']} comparable blobs (dominance {stats['dominance']:.2f}) — "
            "either several figures, or no single creature to animate."
        )

    result = await asyncio.to_thread(upload_build.build_from_upload, raw, suffix)
    return {
        "id": result.id,
        "refused": result.refused,
        "warning": warn,
        "stats": {k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()},
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse((UI / "index.html").read_text())


# Registered last so it only catches paths no real route matched. Without it an unknown
# path fell through to FastAPI's default JSON {"detail":"Not Found"}; now it gets the
# same styled page as every other dead end.
@app.get("/{_path:path}", response_class=HTMLResponse)
def not_found(_path: str):
    return error_page(
        status=404,
        heading="Page not found",
        body="<p>There's nothing at this address. The gallery is the place to start.</p>",
    )


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"gallery: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
