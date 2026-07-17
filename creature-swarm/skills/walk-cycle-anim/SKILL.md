---
name: walk-cycle-anim
description: Animate a child's drawing of a creature as a 2.5D cutout puppet walking around. Use when the swarm has a doodle and needs the {{video}} slot of the field guide filled. Takes the drawing's own pixels — never a reconstruction.
---

# walk-cycle-anim

Turns a child's drawing into a self-contained HTML animation of that creature walking.

The drawing itself walks. We cut it into parts and puppet them as flat layers in a
scene — paper-cutout animation. We never rebuild the creature from a description,
because the entire payload is *"that's my drawing, and it's alive."* A generic mesh
inflated from `body_plan: "blob"` is not that.

## Interface

| | |
|---|---|
| **In** | doodle image (any format PIL reads); Creature Spec `name` + `vibe` if available |
| **Out** | `walk-cycle.html` — one file, drawing inlined base64, zero external deps |
| **Slot** | `{{video}}` in `fieldguide-html`. **Markup, not a `<video>` tag.** |
| **Depends on** | nothing. No `.glb`, no other lane. |

Runs standalone against a fixture rig — no swarm needed:

```bash
./build_walk_cycle.py ../../../examples/drawings/shark-dog.webp \
    --rig rigs/shark-dog.rig.json -o walk-cycle.html
```

## Pipeline

```
doodle → [1] alpha-key → [2] rig (vision) → [3] Canvas2D puppet → walk-cycle.html
```

**1. Alpha-key** (`build_walk_cycle.py:key`, deterministic). White paper → transparent.
Crayon is either dark (outlines) or saturated (fill); paper is bright and grey. That
separates them without a model. Then close gaps, fill interior holes so patchy
colouring doesn't punch through, keep only the largest blob to drop photo shadows and
page-edge specks.

Why this matters: with the paper gone, **part polygons can be sloppy** and no white
box shows. It makes step 2 forgiving, which is the whole reason step 2 is affordable.

**2. Rig** — a vision pass emits `rigs/<name>.rig.json`: image-space polygons, pivots,
parent hierarchy. This is the only hard step and the only one that fails. Hand-authored
fixtures live in `rigs/` (`shark-dog` is the verified reference — copy its schema).

**3. Render** — `template.html`. Parts drawn as polygon-clipped sprites with per-part
transforms; parametric gait with per-leg phase offsets.

## Rig schema

```jsonc
{
  "image": { "w": 580, "h": 404 },
  "name": "Sharkdog", "vibe": "confident, slightly too many fins, no notes",
  "ground_y": 312,              // image-space y of the feet; anchors the puppet
  "parts": [{
    "id": "tail",
    "parent": "body",          // exactly ONE part has parent: null (the root)
    "z": -30,                  // draw order; negative = behind body
    "pivot": [432, 222],       // rotation origin, image space
    "poly": [[398,186], ...],  // cutout outline, image space
    "spring": { "amp": 14, "phase": 0.0, "lag": 0.55 }
  }]
}
```

Per-part behaviours (pick one): `gait` `{phase, swing, lift}` for legs · `spring`
`{amp, phase, lag}` for trailing bits · `chomp` `{amp, period}` for jaws · `blink`
`{period}` for eyes.

### The one rigging rule that matters

**Every polygon must overlap INTO its parent, past the pivot.** A leg rotating 20°
around a hip buried ~15px inside the body never reveals a gap, because there's always
parent geometry behind the joint. This is why we need no inpainting: the occlusion
problem is solved by geometry, for free, instead of by a generative API call inside
the render loop. Where a real hole remains (a fin drawn over the body), fill it
classically — Telea or a local colour sample reads fine against a scribbled fill.

## Cute is the design target, not a side effect

- **Never normalize the child's proportions.** Eight legs, tiny head, one leg longer
  than the others — that all survives to the render. The wonkiness *is* the joke.
- **Spring-lag the trailing bits.** Underdamped, so they overshoot and settle.
- **Squash and stretch** on the body, keyed to the gait.
- **A gait with a slight hitch.** Sterile locomotion is the failure mode.
- **The edge-on turn.** When the puppet reverses, heading sweeps through 90° and the
  cutout goes momentarily flat. That flat-paper pivot is the charm — don't smooth it.

## Known failure modes

Ordered by how they degrade (see `examples/drawings/README.md`):

- **Clean quadruped, side view** (`shark-dog`) — works. Build against this first.
- **Legless drawing** (`pig-face`) — nothing to walk on. Bob-in-place, or bail; do not
  fabricate limbs, since invented legs are *our* drawing, not the child's.
- **Faint grey pencil** (`pencil-creature`) — pencil is low-saturation and only
  moderately dark, so it can fail both key tests and get discarded as paper.
- **No animal at all** (`snowmen-scene`) — largest-blob isolation grabs whatever is
  biggest, which may be scenery. Should be detected and bail.

Graceful degradation: the coordinator omits `{{video}}` when we produce nothing, so
this lane failing never breaks the field guide.
