---
name: walk-cycle-anim
description: "STUB — no working animation code in V1. Full handoff contract below so this can be picked up cold by whoever drives the Animator stretch goal on their own Claude Code instance."
---

# Walk Cycle Animation — STUB

**Status:** stub only. Do not wire the Animator specialist into
`create_specialists.py` until this skill has a real implementation.

## Why this is a stub

Per the design doc, the Animator is a stretch goal that depends on the 3D
Modeler's rig, and V1 must work end-to-end without it (text + 3D viewer
only). This file exists so the work can be picked up cold by a separate
person/session without re-deriving the contract.

## Contract

**Input:**
- The Creature Spec (JSON) — specifically `parts` (for which parts move)
  and `locomotion` (waddle / hop / slither / scuttle / float / other)
- `creature.glb` produced by the 3D Modeler (same primitive assembly the
  3D skill built — the design doc's suggested approach is to rebuild the
  primitives from the Spec rather than trying to rig the exported glb, so
  this can proceed even if glb rigging turns out to be a dead end)

**Output:**
- `walk-cycle.mp4` — short looping clip, offscreen-rendered
- Fills the `{{video}}` slot in `fieldguide-html`'s template (that skill
  already handles omitting this slot if the file doesn't exist, so no
  coordination needed beyond producing the file with the right name)

## Suggested approach (unvalidated — next owner should confirm)

1. Reuse the same trimesh primitive assembly as `procedural-creature-3d`,
   parameterized by `locomotion`.
2. Apply a simple parametric walk cycle: per-leg phase offsets over a gait
   cycle (radial parts get an analogous rotational cycle for non-legged
   locomotion like `slither`/`float`).
3. Render N frames offscreen (trimesh + pyrender or similar).
4. Stitch frames with `ffmpeg` (see `ffmpeg-python` in requirements.txt) ->
   `walk-cycle.mp4`.

## Out of scope for this stub

- Any actual rendering code — none exists yet.
- Rigging the exported `.glb` directly (open question, may not be worth
  pursuing given the rebuild-from-Spec alternative above).

## Definition of done

A person with zero prior context on this repo should be able to read this
file alone, look at `schemas/creature-spec.schema.json`, and start writing
`build.py` without needing to ask anyone a clarifying question about the
contract. If that's not true, this stub isn't finished — fix the stub, not
just the code.
