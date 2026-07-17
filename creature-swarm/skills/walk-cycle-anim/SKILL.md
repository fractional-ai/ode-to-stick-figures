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
| **In** | doodle image (any format PIL reads) + optional free text: `name`, `vibe`, `movement`, and the `locomotion`/`speed` they imply |
| **Out** | `walk-cycle.html` — one file, drawing inlined base64, zero external deps |
| **Slot** | `{{video}}` in `fieldguide-html`. **Markup, not a `<video>` tag.** |
| **Depends on** | nothing. No `.glb`, no other lane. |

### Free text is welcome — at author time, not render time

The renderer wants numbers. Prose is never parsed there; asking it to interpret
"lurches along, stops to sniff things" would be the worst of both worlds. Instead the
**vision pass that authors the rig** takes the description and emits `locomotion`,
`speed`, and amplitudes — one place, once, where a model is already looking at the
drawing. Everything downstream is deterministic.

The frozen Creature Spec already carries all of it, so **no schema change is needed**:

| Spec field | drives |
|---|---|
| `locomotion` | which movement model (below) |
| `palette` | the colouring (see *Colour*) |
| `vibe` | cadence, bounce, how manic it reads |
| `body_plan.symmetry` | per-limb phase distribution |
| `name` | caption |

Any of these can be overridden per run without editing the rig:

```bash
./build_walk_cycle.py ../../../examples/drawings/bee.webp --rig rigs/bee.rig.json --color \
    --name "Bumbling Behemoth (Apis enormis)" --vibe "far too large for those legs" \
    --movement "flies in lazy loops, never quite lands" \
    --locomotion fly --speed 0.75 --faces right -o /tmp/wc.html
```

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

Per-part behaviours (pick one): `gait` `{phase, swing, lift}` for legs · `flap`
`{amp, phase, rest}` for wings · `spring` `{amp, phase, lag}` for trailing bits ·
`chomp` `{amp, period}` for jaws · `blink` `{period}` for eyes.

## Movement models — `locomotion`

Every creature moving at one speed with one gait reads as a rigged puppet show. A stiff
rectangle travels nothing like a bird, and that difference is most of the charm. Each
model owns its own speed, path through the air, and body attitude.

| `locomotion` | what it does | for |
|---|---|---|
| `walk` | legs cycle in phase-offset pairs, body bobs, stays grounded | quadrupeds, bipeds |
| `stumble` | **no gait — rotation IS the locomotion.** A rigid body rocks corner to corner (asymmetric, so it tips and catches rather than swinging like a metronome) and lurches forward in pulses | the pop-tart; anything jointless |
| `fly` | wings flap (asymmetric — the downstroke is the hard one), body rides a sine through the air, never touches ground, shadow stays below and fades with altitude | birds, the bee |
| `float` | barely travels; drifts on a slow sine and bobs gently in place | balloon-shaped creatures |
| `hop` | parabolic arcs with squash on landing | legless bobbers |

Set `speed` to multiply the model's base. `faces: "right"` for right-facing drawings —
without it they **moonwalk**, because heading 0 means "the drawing's natural facing"
and the default assumes left.

Squash only applies to models that touch the ground: it reads as weight, and a flyer
has nothing to push against.

## Colour — `colorize` / `palette`

`--color` floods bright crayon into the regions **the child's own strokes already
enclose**. It's a colouring book: we never add a stroke or reshape a line, only the
white between them changes. Regions fill largest-first, so `palette[0]` lands on the
biggest shape — with a Spec `palette`, that's the creature's dominant colour.

**It no-ops on drawings that already have colour**, so a child's own choices are never
overridden.

Two clear areas want two entries. The pop-tart's frosting and pastry border are
separate regions, so `"palette": ["#f7cfe0", "#d99a52"]` gives pink frosting inside a
tan border. Note the ink mask is closed 5×5 before regions are split — children's
outlines have gaps, and one gap merges two areas into one colour.

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
