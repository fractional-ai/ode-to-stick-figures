#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["anthropic", "pillow", "numpy", "scipy", "python-dotenv"]
# ///
# Kept deliberately — see the note in build_walk_cycle.py. This skill has to run from a
# bare copy of its own directory, so it declares its own dependencies.
"""doodle -> rig.json, via a vision pass. The one genuinely unsolved step.

Everything else in this lane is deterministic. Deciding "where are this creature's
knees" requires interpreting a child's intent, which is exactly what no
off-the-shelf segmenter does and a VLM does well.

Two things make it work at all:

  * We show the model the KEYED cutout, not the photo. It sees precisely what the
    renderer will draw — no paper, no shadows, no scenery to be distracted by.
  * We overlay a labelled coordinate grid. Asking for pixel coordinates off a bare
    image invites plausible-looking guesses; with a ruler in the picture the model
    reads them off. This is the same crutch a human rigger would want.

    ./rig_from_image.py ../../../examples/drawings/sharpie-bird.jpg
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from build_walk_cycle import key  # noqa: E402

MODEL = "claude-sonnet-5"

PROMPT = """\
You are rigging a child's drawing so it can be animated as a 2.5D cutout puppet — \
flat parts, cut from this exact image, hinged at joints and puppeted like paper.

The image is the ALPHA-KEYED cutout: the paper is already removed, and what you see \
is exactly what will be drawn. It is {w}x{h} pixels. A coordinate grid is overlaid \
to read positions off — red vertical lines and blue horizontal lines every 50px, \
labelled. USE THE GRID. Give coordinates in this {w}x{h} space.

Emit ONLY a JSON object, no prose, no markdown fence:

{{
  "name": "invented name for this creature, warm and a bit silly",
  "vibe": "one-line personality read",
  "faces": "left" | "right",
  "ground_y": <int: y where the feet/base meet the ground>,
  "parts": [
    {{
      "id": "body",
      "parent": null,
      "z": 0,
      "pivot": [x, y],
      "poly": [[x,y], [x,y], ...]
    }},
    {{
      "id": "legNearFront", "parent": "body", "z": 10,
      "pivot": [x, y], "poly": [[x,y], ...],
      "gait": {{"phase": 0.0, "swing": 16, "lift": 6}}
    }}
  ]
}}

RULES — these are not style preferences, they are what makes it not break:

1. EXACTLY ONE part has "parent": null. That is the torso/root. Everything else \
parents to it by id.
2. EVERY polygon must OVERLAP INTO ITS PARENT, past the pivot, by ~15px. A limb \
rotating around a hip buried inside the body never reveals a gap. Polygons that stop \
at the joint tear open when they rotate.
3. Polygons may be loose — the paper is transparent, so slop costs nothing. But keep \
them tight enough not to swallow a NEIGHBOURING limb. Adjacent legs are the risk.
4. Pivots go where the part EXITS the parent's outline, not deep inside it. A pivot \
inside the parent polygon splits the part in two.
5. z: negative = behind the body (far limbs, tail, back fins). Positive = in front \
(near limbs, jaw, eyes).

BEHAVIOURS — attach at most one per part:
  "gait":   {{"phase": <0 or 3.14159>, "swing": 12-20, "lift": 4-8}}  -> LEGS ONLY. \
Opposed phases for alternating limbs (front-left with back-right).
  "spring": {{"amp": 5-15, "phase": 0.0-3.0, "lag": 0.3-0.6}}  -> trailing bits that \
should lag and overshoot: tails, ears, wings, antennae, fins.
  "chomp":  {{"amp": 6-10, "period": 2.6}}  -> a hinged jaw, if there is one.
  "blink":  {{"period": 3.7}}  -> an eye, if it is a distinct shape.

HONESTY REQUIREMENTS — these matter more than producing a rig:

* Do NOT invent anatomy. Every part must be a cutout of pixels the child actually \
drew. If there are no legs, emit no "gait" parts — a legless creature bobs in place, \
and that is correct and charming. Fabricated limbs would be OUR drawing composited \
onto a child's, which destroys the entire point.
* "faces" must match the drawing. Get this wrong and it moonwalks.
* If this image contains NO animal/creature at all (a scene, an object, scenery), \
return exactly: {{"refuse": true, "refuse_reason": "<why, one line>"}}
* If it contains SEVERAL separate figures, rig the single most prominent one and add \
"note": "<what you ignored>".
"""


def grid_overlay(keyed: Image.Image) -> Image.Image:
    """Flatten onto white and draw a labelled 50px ruler over it."""
    flat = Image.new("RGB", keyed.size, (255, 255, 255))
    flat.paste(keyed, (0, 0), keyed)
    d = ImageDraw.Draw(flat)
    w, h = flat.size
    for x in range(0, w, 50):
        d.line([(x, 0), (x, h)], fill=(255, 70, 70), width=1)
        d.text((x + 2, 2), str(x), fill=(220, 0, 0))
    for y in range(0, h, 50):
        d.line([(0, y), (w, y)], fill=(70, 140, 255), width=1)
        d.text((2, y + 2), str(y), fill=(0, 80, 220))
    return flat


def validate(spec: dict) -> list[str]:
    """Catch the failures that render as garbage rather than as an error."""
    if spec.get("refuse"):
        return []
    problems = []
    parts = spec.get("parts") or []
    if not parts:
        return ["no parts"]
    roots = [p for p in parts if p.get("parent") is None]
    if len(roots) != 1:
        problems.append(f"need exactly 1 root part, got {len(roots)}")
    ids = {p.get("id") for p in parts}
    for p in parts:
        pid = p.get("id", "?")
        if p.get("parent") is not None and p["parent"] not in ids:
            problems.append(f"{pid}: parent '{p['parent']}' does not exist")
        if len(p.get("poly") or []) < 3:
            problems.append(f"{pid}: polygon needs >=3 points")
        if len(p.get("pivot") or []) != 2:
            problems.append(f"{pid}: pivot must be [x, y]")
    if not isinstance(spec.get("ground_y"), (int, float)):
        problems.append("ground_y must be a number")
    return problems


def rig_from_image(doodle: Path, model: str = MODEL) -> dict:
    from anthropic import Anthropic

    keyed, stats = key(Image.open(doodle))
    buf = io.BytesIO()
    grid_overlay(keyed).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=model,
        max_tokens=16000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    },
                    {"type": "text", "text": PROMPT.format(w=keyed.width, h=keyed.height)},
                ],
            }
        ],
    )
    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    spec = json.loads(text)

    spec["source"] = str(doodle)
    spec["image"] = {"w": keyed.width, "h": keyed.height}
    spec["_key_stats"] = {k: round(v, 3) if isinstance(v, float) else v for k, v in stats.items()}
    return spec


def main() -> None:
    from dotenv import load_dotenv

    # HERE is skills/walk-cycle-anim, so parents[1] is the repo root.
    for env in (HERE.parents[1] / ".env", HERE.parents[2] / ".env"):
        if env.is_file():
            load_dotenv(env)
            break

    ap = argparse.ArgumentParser()
    ap.add_argument("doodle", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    spec = rig_from_image(args.doodle, args.model)
    if spec.get("refuse"):
        print(f"REFUSED: {spec.get('refuse_reason')}")
    problems = validate(spec)
    if problems:
        print("INVALID RIG:", *problems, sep="\n  ")

    out = args.out or (HERE / "rigs" / f"{args.doodle.stem}.rig.json")
    out.write_text(json.dumps(spec, indent=2))
    print(f"{out}  ({len(spec.get('parts', []))} parts, faces={spec.get('faces')})")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
