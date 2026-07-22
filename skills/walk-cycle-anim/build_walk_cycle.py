#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
# Keep this block even though the repo has a pyproject.toml. SKILL.md documents this file
# as an agent-invocable entry point, and an agent given the skill directory gets these two
# scripts and nothing else — no pyproject to resolve against. The duplicated floors are the
# price of that portability; a skill that only runs from inside this checkout isn't a skill.
"""doodle + rig -> self-contained walk-cycle.html

Two steps, both local and deterministic:

  1. key()   strip the white paper to transparency so part polygons can be loose
  2. build() inline the keyed PNG + rig as base64/JSON into a single HTML file

Runs standalone against a fixture rig, no swarm and no other lane required. Run from
this directory — both paths below are relative to it:

    ./build_walk_cycle.py ../../examples/drawings/shark-dog.webp \
        --rig rigs/shark-dog.rig.json -o walk-cycle.html
"""

from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as nd

HERE = Path(__file__).parent


def key(img: Image.Image, keep: int = 1) -> tuple[Image.Image, dict]:
    """Traced wrapper around the alpha key. See _key_impl for the actual algorithm.

    This is the hot spot of the whole upload, and it was invisible: the cost scales
    with pixel count, and nothing downscales a phone photo, so the same call that
    takes 0.3s on a bundled drawing takes 14s+ on a 12MP JPEG. One upload runs it
    four times. That combination timed out a production upload at 180s and the logs
    said only "Task timed out" — see issue #88. Now the span carries the dimensions,
    so the next time this is slow the trace says why.
    """
    import logfire

    mp = (img.width * img.height) / 1e6
    with logfire.span(
        "alpha key {width}x{height} ({megapixels:.1f}MP)",
        width=img.width,
        height=img.height,
        megapixels=mp,
        keep=keep,
    ) as span:
        keyed, stats = _key_impl(img, keep=keep)
        span.set_attribute("blobs", stats.get("blobs"))
        span.set_attribute("kept_frac", stats.get("kept_frac"))
        return keyed, stats


def _key_impl(img: Image.Image, keep: int = 1) -> tuple[Image.Image, dict]:
    """White paper -> alpha 0, creature -> alpha 255, interior holes filled.

    Ink is either dark (outlines) or saturated (crayon fill); paper is bright and
    neutral. That separates them without a model — but every constant here was
    earned the hard way, so read the notes before tuning:

    1. FLATTEN THE ILLUMINATION FIRST, LOCALLY. Two separate things break here and
       one fix handles both. (a) Warm light gives *blank paper* a saturation of
       40-70, over the colour threshold, so the key fires on the page and the whole
       sheet returns as one blob. (b) A cast shadow is darker than paper, so it
       passes the ink test and gets keyed in as part of the creature — on
       sharpie-horse a shadow became a huge blob fused to the animal. A single
       global illuminant can't fix (b) because the gradient is spatial. So estimate
       paper LOCALLY: max-filter away the strokes, blur to get a smooth paper
       model, divide by it. Shadows and colour cast both flatten out, and every
       downstream threshold gets a neutral page to work against.
    2. DERIVE THE INK CUTOFF PER IMAGE. A global luminance constant tuned on crayon
       deletes grey pencil (paper 240, pencil only reaches 141 — it fails both
       tests and is discarded as background). Anchor it to this page's own paper.
    3. CLOSE BEFORE FILLING, AND CLOSE HARD. Line art is a sparse stroke skeleton,
       not a blob. If closing can't bridge the strokes into a closed region, then
       fill_holes has nothing to fill and largest-blob keeps one stray fragment of
       the drawing. A 9x9 kernel left a bird headless; 13x13 bridges it.
    4. NO OPENING. A 3x3 opening is wider than a thin marker stroke and erases it
       (one bird lost its head this way: 84px -> 9px). Largest-blob despeckles
       adequately on its own.

    Returns (rgba, stats). `stats` reports ink coverage, blob count and dominance so
    a caller can decide whether the drawing is riggable at all. `keep` selects how
    many of the largest blobs survive — >1 for drawings with several figures.
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)

    # Local paper model: max-filter removes the strokes (ink is dark, so the local
    # max is paper), then a blur smooths it into an illumination field. Dividing by
    # it flattens shadow gradients AND colour cast at once. Kernel must exceed the
    # widest stroke or ink survives into the model and erases itself.
    k = max(9, min(a.shape[0], a.shape[1]) // 16)
    wb = np.empty_like(a)
    for c in range(3):
        paper_c = nd.maximum_filter(a[..., c], size=k)
        paper_c = nd.gaussian_filter(paper_c, sigma=k / 2.0)
        wb[..., c] = a[..., c] / np.maximum(paper_c, 1.0) * 245.0
    wb = np.clip(wb, 0, 255)

    lum = 0.299 * wb[..., 0] + 0.587 * wb[..., 1] + 0.114 * wb[..., 2]
    sat = wb.max(-1) - wb.min(-1)

    paper = float(np.percentile(lum, 92))
    inkness = np.clip(((paper - 26) - lum) / 60, 0, 1)
    colorness = np.clip((sat - 20) / 35, 0, 1)
    mask = np.maximum(inkness, colorness) > 0.35
    ink_frac = float(mask.mean())

    mask = nd.binary_closing(mask, np.ones((13, 13)))
    mask = nd.binary_fill_holes(mask)

    lab, n = nd.label(mask)
    stats = {"ink_frac": ink_frac, "blobs": 0, "dominance": 0.0, "figures": 0}
    if n:
        sizes = nd.sum(mask, lab, range(1, n + 1))
        total = sizes.sum()
        order = np.argsort(sizes)[::-1]
        stats["blobs"] = int((sizes > 0.05 * total).sum())
        stats["dominance"] = float(sizes.max() / total) if total else 0.0
        winners = [i + 1 for i in order[:keep] if sizes[i] > 0.02 * total]
        stats["figures"] = len(winners)
        mask = np.isin(lab, winners)
    mask = nd.binary_dilation(mask, np.ones((3, 3)))
    stats["kept_frac"] = float(mask.mean())

    alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    return Image.fromarray(np.dstack([a.astype(np.uint8), np.asarray(alpha)]), "RGBA"), stats


# Bright, saturated, unashamed. A child's crayon box, not a designer's palette —
# realism is not the goal and would actively hurt.
# The 4x2 grid is the point: one colour per line reads as a list, not as a box of crayons.
# The directive below has to be bare — a trailing comment on it makes ruff ignore it.
# fmt: off
CRAYON = [
    "#ff5964", "#ffb400", "#ffe14d", "#5ac85a",
    "#3aa7ff", "#a05ae0", "#ff8fc7", "#ff8a3d",
]
# fmt: on


def _hex(c: str) -> np.ndarray:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return np.array([int(c[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def colorize(rgba: Image.Image, palette: list[str] | None = None) -> Image.Image:
    """Flood bright colour into the enclosed regions of a mono line drawing.

    This is a colouring book, and that is the point. We find the regions the child's
    own strokes already enclose and fill each one — we never invent strokes or
    reshape anything. The linework stays exactly where they put it; only the white
    between it changes. A sharpie doodle keeps its identity and stops being grey.

    No-ops on drawings that are already coloured, so crayon art is left alone.
    """
    a = np.asarray(rgba).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    inside = alpha > 128
    if not inside.any():
        return rgba

    sat = rgb.max(-1) - rgb.min(-1)
    if float(np.median(sat[inside])) > 28:
        return rgba  # already coloured; don't touch the child's own colour choices

    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    paper = float(np.percentile(lum[inside], 80))
    ink = (lum < paper - 45) & inside
    # Close the strokes before splitting regions. Children's outlines have gaps, and
    # one gap merges two areas into one — the pop-tart's frosting line leaks into its
    # pastry border, so both take a single colour instead of two. A 5x5 bridges the
    # gap without closing the deliberate spaces between separate parts.
    ink = nd.binary_closing(ink, np.ones((5, 5)))
    regions = inside & ~nd.binary_dilation(ink, np.ones((3, 3)))

    lab, n = nd.label(regions)
    if not n:
        return rgba
    sizes = nd.sum(regions, lab, range(1, n + 1))
    pal = [_hex(c) for c in (palette or CRAYON)]
    out = rgb.copy()
    # Largest region first so the biggest shape gets the first (most dominant)
    # palette entry — with a Spec palette, that means the creature's own colour.
    for rank, idx in enumerate(np.argsort(sizes)[::-1]):
        if sizes[idx] < 40:
            continue
        m = lab == (idx + 1)
        col = pal[rank % len(pal)]
        # Multiply rather than replace: keeps paper tooth and stroke edges, so it
        # reads as crayon laid over paper instead of a flat vector fill.
        out[m] = np.clip(rgb[m] / 255.0 * col, 0, 255)

    return Image.fromarray(np.dstack([out.astype(np.uint8), alpha.astype(np.uint8)]), "RGBA")


LOCOMOTIONS = ("walk", "stumble", "fly", "float", "hop", "slither")
ENVIRONMENTS = ("meadow", "ocean", "sky", "garden", "forest", "kitchen", "snow", "cave")


def build(
    doodle: Path,
    rig: Path,
    out: Path,
    keep: int = 1,
    color: bool = False,
    overrides: dict | None = None,
) -> tuple[Path, dict]:
    spec = json.loads(rig.read_text())
    # Free text (name / vibe / movement) and the locomotion+speed it implies can be
    # supplied per-run without editing the rig, so the Creature Spec can drive the
    # animation directly. Prose is deliberately NOT parsed here: the renderer wants
    # numbers, and the mapping from "stumbles along, stops to sniff things" onto a
    # model plus amplitudes belongs to the vision pass that authors the rig — one
    # place, once, where a model is already reading the drawing.
    for k, v in (overrides or {}).items():
        if v is not None:
            spec[k] = v
    keyed, stats = key(Image.open(doodle), keep=max(keep, spec.get("figures", 1)))
    if color or spec.get("colorize"):
        keyed = colorize(keyed, spec.get("palette"))

    buf = io.BytesIO()
    keyed.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()
    spec["image"] = {"w": keyed.width, "h": keyed.height}

    html = (HERE / "template.html").read_text()
    html = html.replace("__RIG_JSON__", json.dumps(spec))
    html = html.replace("__DOODLE_B64__", b64)
    out.write_text(html)
    return out, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("doodle", type=Path)
    ap.add_argument("--rig", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, default=Path("walk-cycle.html"))
    ap.add_argument(
        "--keep",
        type=int,
        default=1,
        help="how many of the largest blobs to keep; >1 for multi-figure drawings",
    )
    ap.add_argument(
        "--color",
        action="store_true",
        help="flood bright crayon colour into a mono line drawing's enclosed regions "
        "(no-ops if the drawing is already coloured)",
    )
    ap.add_argument("--name", help="Creature Spec `name` — free text, shown as caption")
    ap.add_argument("--vibe", help="Creature Spec `vibe` — free text, shown as caption")
    ap.add_argument(
        "--movement",
        help="free-text movement description, e.g. 'lurches, stops to sniff things'. "
        "Recorded on the rig for provenance; the vision pass turns it into "
        "--locomotion/--speed. Not parsed here.",
    )
    ap.add_argument(
        "--locomotion",
        choices=LOCOMOTIONS,
        help="movement model: walk (legs cycle) | stumble (rigid body rocks itself "
        "forward in lurches) | fly (wings flap, rides a sine through the air) | "
        "float (drifts and bobs, barely travels) | hop (parabolic arcs)",
    )
    ap.add_argument("--speed", type=float, help="speed multiplier on the model's base")
    ap.add_argument(
        "--environment",
        choices=ENVIRONMENTS,
        help="background world: every creature on the same strip of grass makes the "
        "animations read as one animation with the sprite swapped",
    )
    ap.add_argument(
        "--faces",
        choices=("left", "right"),
        help="which way the drawing points; 'right' stops it moonwalking",
    )
    args = ap.parse_args()

    out, s = build(
        args.doodle,
        args.rig,
        args.out,
        keep=args.keep,
        color=args.color,
        overrides={
            "name": args.name,
            "vibe": args.vibe,
            "movement": args.movement,
            "locomotion": args.locomotion,
            "speed": args.speed,
            "faces": args.faces,
            "environment": args.environment,
        },
    )
    kb = out.stat().st_size / 1024
    print(f"{out}  ({kb:.0f} KB, self-contained)")
    print(
        f"  key: ink={s['ink_frac']:.2f} blobs={s['blobs']} "
        f"dominance={s['dominance']:.2f} kept={s['kept_frac']:.2f} "
        f"figures={s['figures']}"
    )
    # Loud, not silent. A drawing with no isolable subject still builds and renders
    # plausible-looking garbage (paper slabs sliding sideways) at exit 0 — that is
    # the worst failure we can hand an audience. Blob stats can't tell "no animal"
    # from "a big animal", so this warns rather than gates; the semantic call
    # belongs to the vision pass.
    if s["blobs"] >= 3 and s["dominance"] < 0.80:
        print(
            f"  WARNING: {s['blobs']} comparable blobs, dominance "
            f"{s['dominance']:.2f} — no single dominant subject. Either this drawing "
            f"has several figures (pass --keep N) or it has no animal in it at all "
            f"(the coordinator should omit the slot). Look at the output."
        )


if __name__ == "__main__":
    main()
