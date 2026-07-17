#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow", "numpy", "scipy"]
# ///
"""doodle + rig -> self-contained walk-cycle.html

Two steps, both local and deterministic:

  1. key()   strip the white paper to transparency so part polygons can be loose
  2. build() inline the keyed PNG + rig as base64/JSON into a single HTML file

Runs standalone against a fixture rig, no swarm and no other lane required:

    ./build_walk_cycle.py examples/drawings/shark-dog.webp \
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
    """White paper -> alpha 0, creature -> alpha 255, interior holes filled.

    Ink is either dark (outlines) or saturated (crayon fill); paper is bright and
    neutral. That separates them without a model — but every constant here was
    earned the hard way, so read the notes before tuning:

    1. WHITE BALANCE FIRST. A phone photo under warm light gives *blank paper* a
       saturation of 40-70, well over the colour threshold, so the key fires on the
       page and the whole sheet comes back as one blob. Normalising each channel by
       its own p95 illuminant returns paper to neutral. Without this, real phone
       photos are silently unusable.
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

    illum = np.array([np.percentile(a[..., c], 95) for c in range(3)])
    illum[illum < 1] = 1
    wb = np.clip(a / illum * 245.0, 0, 255)

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

    alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.8)
    )
    return Image.fromarray(
        np.dstack([a.astype(np.uint8), np.asarray(alpha)]), "RGBA"
    ), stats


def build(doodle: Path, rig: Path, out: Path, keep: int = 1) -> tuple[Path, dict]:
    spec = json.loads(rig.read_text())
    keyed, stats = key(Image.open(doodle), keep=max(keep, spec.get("figures", 1)))

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
    args = ap.parse_args()

    out, s = build(args.doodle, args.rig, args.out, keep=args.keep)
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
