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


def key(img: Image.Image) -> Image.Image:
    """White paper -> alpha 0, creature -> alpha 255, interior holes filled.

    Crayon is either dark (ink outlines) or saturated (the fill). Paper is bright and
    grey. That separates them without a model. We then close gaps, fill interior holes
    so patchy colouring doesn't punch through, and keep only the largest blob, which
    drops photo shadows and stray specks at the edges of the page.
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    sat = a.max(-1) - a.min(-1)

    inkness = np.clip((175 - lum) / 60, 0, 1)
    colorness = np.clip((sat - 20) / 35, 0, 1)
    mask = np.maximum(inkness, colorness) > 0.35

    mask = nd.binary_closing(mask, np.ones((9, 9)))
    mask = nd.binary_fill_holes(mask)
    mask = nd.binary_opening(mask, np.ones((3, 3)))
    lab, n = nd.label(mask)
    if n:
        sizes = nd.sum(mask, lab, range(1, n + 1))
        mask = lab == (int(np.argmax(sizes)) + 1)
    mask = nd.binary_dilation(mask, np.ones((3, 3)))

    alpha = Image.fromarray((mask * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.8)
    )
    return Image.fromarray(
        np.dstack([a.astype(np.uint8), np.asarray(alpha)]), "RGBA"
    )


def build(doodle: Path, rig: Path, out: Path) -> Path:
    keyed = key(Image.open(doodle))
    buf = io.BytesIO()
    keyed.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode()

    spec = json.loads(rig.read_text())
    spec["image"] = {"w": keyed.width, "h": keyed.height}

    html = (HERE / "template.html").read_text()
    html = html.replace("__RIG_JSON__", json.dumps(spec))
    html = html.replace("__DOODLE_B64__", b64)
    out.write_text(html)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("doodle", type=Path)
    ap.add_argument("--rig", type=Path, required=True)
    ap.add_argument("-o", "--out", type=Path, default=Path("walk-cycle.html"))
    args = ap.parse_args()

    out = build(args.doodle, args.rig, args.out)
    kb = out.stat().st_size / 1024
    print(f"{out}  ({kb:.0f} KB, self-contained)")


if __name__ == "__main__":
    main()
