# Creature Swarm — Design

**Date:** 2026-07-17
**Status:** Approved (design), pending implementation plan
**Base:** Built on the `ode-to-stick-figures` managed-agents pattern (coordinator + specialists + Skills)

## Purpose

Take a bad drawing of a made-up animal and spin off a swarm of specialist agents
that each treat it with complete seriousness, then assemble the results into a
single self-contained HTML "field guide" page. The comedy is a rigorous,
partner-firm-style pipeline producing an authoritative dossier about a crayon blob.

## Concept landed

Same architecture as the workshop's Option 3 (Specialist Swarm): a coordinator
fans work out to parallel specialist sub-agents, each with its own Skill, on
**Claude Managed Agents (multi-agent)**. Committed to the managed-agents preview —
no local-orchestration fallback in scope.

## Topology

```
                 ┌─────────────────────────────────────────┐
   doodle.png ──▶│  Coordinator ("Field Editor")            │
                 └─────────────────────────────────────────┘
                    │ 1. serial            │ 3. assemble
                    ▼                       ▼
          ┌──────────────────┐    fieldguide-html skill
          │ Field Interpreter│         → field-guide.html
          │  (vision)        │
          └──────────────────┘
                    │ Creature Spec (JSON + prose)
                    │ 2. parallel fan-out
      ┌─────────────┼─────────────┬──────────────┬─────────────┐
      ▼             ▼             ▼              ▼             ▼
 ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐
 │Biologist│  │ Habitat  │  │ Society  │  │3D Modeler │  │ Animator │
 └─────────┘  └──────────┘  └──────────┘  └───────────┘  └──────────┘
                                                │              │ doodle.png
                                          creature.glb         │ (own vision pass)
                                                               ▼
                                                        walk-cycle.html
```

- **Phase 1 (serial):** Coordinator delegates to the Field Interpreter, which reads
  the doodle once and emits the canonical **Creature Spec**.
- **Phase 2 (parallel):** Coordinator fans the Spec out to Biologist, Habitat,
  Society, 3D Modeler, and Animator simultaneously.
- **Phase 3 (assemble):** Coordinator runs the `fieldguide-html` skill to stitch all
  outputs into one portable HTML page.

**Revision 2026-07-17 (Animator lane):** the Animator no longer derives from the 3D
Modeler's `.glb`, and no longer renders an `.mp4`. It is a **2.5D cutout puppet**
built from the doodle's own pixels, and it runs in the Phase 2 fan-out like any other
specialist. Rationale and consequences in *Animation approach* below.

Approach chosen: **A — coordinator assembles.** Upgradeable later to **B** (lift
assembly into a dedicated Publisher/Curator agent) without changing the contracts
below.

## Roster & contracts

| Agent | Model tier | Skill | Input | Output |
|---|---|---|---|---|
| **Field Interpreter** | sonnet (vision) | — | doodle image | `creature-spec.json` + prose |
| **Biologist** | sonnet | `creature-biology` | Creature Spec | markdown section |
| **Habitat** | sonnet | `habitat-ecology` | Creature Spec | markdown section |
| **Society** | sonnet | `folklore-society` (owner's discretion) | Creature Spec | markdown section |
| **3D Modeler** | sonnet | `procedural-creature-3d` | Creature Spec | `creature.glb` |
| **Animator** | sonnet (vision) | `walk-cycle-anim` | **doodle image** + Creature Spec (for `name`/`vibe` only) | `walk-cycle.html` (self-contained) |
| **Coordinator** | opus | `fieldguide-html` | all of the above | `field-guide.html` |

Each agent is an independently ownable lane. The two shared files to **freeze first**
are the Creature Spec schema and the `fieldguide-html` slot contract.

## Contract 1 — Creature Spec (consistency seam)

The Interpreter emits one structured JSON that every downstream agent keys off, so
all agents describe the *same* creature. Text agents mine the descriptive half; the
3D Modeler treats the structural half as literal build instructions.

```json
{
  "name": "invented common + mock-Latin name",
  "body_plan": {
    "core_shape": "sphere|ovoid|slab|...",
    "symmetry": "bilateral|radial",
    "size_est_m": 0.4
  },
  "parts": [
    { "type": "leg", "count": 6, "shape": "...", "placement": "..." },
    { "type": "eyestalk", "count": 2, "shape": "...", "placement": "..." }
  ],
  "palette": ["#hex", "..."],
  "distinctive_features": ["forked tail", "bioluminescent spots"],
  "locomotion": "waddle|hop|slither",
  "vibe": "one-line personality"
}
```

- **Text consumers** (Biologist/Habitat/Society): `name`, `distinctive_features`,
  `vibe`, plus loose reference to `parts`/`palette`.
- **Structural consumer** (3D Modeler): `body_plan`, `parts`, `palette`,
  `locomotion` as build parameters.
- **Animator:** reads only `name`/`vibe`. Its geometry comes from its own vision pass
  over the doodle, because image-space polygons and pivots aren't expressible in this
  Spec — and deliberately so: the seam stays frozen and the Interpreter needs no edits.

## Contract 2 — `fieldguide-html` slots (integration seam)

A fixed, self-contained HTML template with named slots. The coordinator only fills
slots; it never freehands markup. All assets inlined (base64) so the page is one
portable file.

Slots:
- `{{creature_name}}`, `{{tagline}}`
- `{{doodle_img}}` — original drawing, inlined base64
- `{{biology_html}}`, `{{habitat_html}}`, `{{society_html}}` — rendered from each
  markdown section
- `{{model_viewer}}` — `<model-viewer src="creature.glb">` (script via CDN); omitted
  if no `.glb`
- `{{video}}` — self-contained HTML/canvas walk-cycle block (**not** a `<video>` tag —
  see *Animation approach*); omitted if the Animator produced nothing

## Procedural media approach

- **3D:** Python `trimesh` in the sandbox composes primitives (spheres, capsules,
  cylinders) from `body_plan`/`parts`, colors them from `palette`, exports
  `creature.glb`. Deliberately lumpy — a serious pipeline producing a
  crayon-faithful blob.
- **Animation:** superseded — see *Animation approach* below. Not derived from the
  `.glb`, and not an `.mp4`.

## Animation approach — 2.5D cutout puppet

**Revised 2026-07-17. Supersedes the "reuse the 3D rig, render frames → ffmpeg" plan.**

The Animator cuts the doodle into parts and puppets them as flat cutouts in a 3D
scene — paper-cutout animation, Paper Mario / Monty Python. The child's actual
linework is what walks around.

**Why this replaced the 3D-derived video:**

1. **It keeps the drawing.** Rebuilding the creature from `body_plan`/`parts` throws
   the pixels away and renders a generic primitive blob. The 2.5D puppet animates the
   crayon itself — wonky proportions, visible strokes, teeth and all. "That's *my*
   drawing, and it's *alive*" is the payload.
2. **No headless GL.** `trimesh` + `pyrender` + OSMesa/EGL offscreen rendering was the
   single largest schedule risk in the original plan and contributes nothing to the
   joke. This path has no render dependency at all.
3. **It decouples the lane.** No dependency on the 3D Modeler returning.

**Pipeline (entirely within this lane):**

```
doodle.png
   │  1. alpha-key: white paper → transparent (luminance + saturation, hole-fill)
   ▼
keyed.png  (creature isolated, crayon texture preserved)
   │  2. vision pass → rig.json: image-space part polygons, pivots, parent hierarchy
   ▼
rig.json
   │  3. Canvas2D renderer: parts drawn as clipped sprites, per-part transforms,
   │     parametric gait with per-leg phase offsets
   ▼
walk-cycle.html  (self-contained, drawing inlined base64, zero external deps)
```

Step 2 is the only hard step and the only one that can fail. Fallback if the polygons
come back garbage: a drag-the-joints editor, or a hand-authored rig (`shark-dog` ships
with one as a fixture).

**Cute is the design target, not a side effect.** Never normalize the child's
proportions — the wonkiness *is* the joke. Cuteness comes from spring-damped
secondary motion (tail, fins lag the body), squash-and-stretch with overshoot, eye
blinks, a soft contact-shadow, and a gait with a slight hitch in it. Sterile
locomotion is the failure mode.

**Contract change — `{{video}}` slot.** The Animator emits a self-contained HTML/canvas
block, not an `.mp4`, so `{{video}}` receives markup rather than a `<video>` tag. The
coordinator only fills slots and already omits the slot when the artifact is missing,
so the blast radius is this one slot. An `.mp4` remains derivable later if the demo
needs a file (screenshot frames → `ffmpeg`) — but the live canvas is the better demo,
since it's interactive and can't fail to play in the room.

**Not affected:** the Creature Spec schema (Contract 1) is unchanged. The Animator does
its own vision pass for image-space geometry rather than extending the Spec, precisely
so the frozen seam stays frozen and the Interpreter lane needs no edits.

## Repo structure

The layout this section planned is obsolete — the `creature-swarm/` folder it
describes was dissolved into the repo root, and several files it lists were never
written or have since been deleted. See the README for the tree as it actually is.
Kept as a section header only so the surrounding rationale still reads in order.

## Team split

Natural ownership lanes: one person per specialist+skill pair; one owns the
Interpreter + Spec schema; one owns the `fieldguide-html` template + coordinator
assembly. The Spec schema and slot contract are frozen first so lanes proceed in
parallel.

The `walk-cycle-anim` lane is **owned and in progress** (Hugh, driving his own Claude
Code instance) — no longer a stub. Its contract: input = doodle image (+ Spec `name`/
`vibe`), output = `walk-cycle.html`, fills the `{{video}}` slot. It depends on no other
lane, so it can land independently of the 3D Modeler.

## Error handling & degradation

- **Consistency guard:** a specialist that can't parse the Spec asks the coordinator
  for a re-brief rather than inventing a divergent creature.
- **Graceful degradation:** coordinator omits `{{model_viewer}}` / `{{video}}` when
  those artifacts are missing, so a text-only run still yields a valid page (mirrors
  the original repo's "docx if available, else markdown" ethos).

## Testing

Each skill's code path (3D build, HTML fill, later the walk-cycle render) is runnable
standalone against a fixture Creature Spec without spinning the whole swarm, so each
teammate can test their lane in isolation.

## Demo

- **Monitor 1:** the coordinator event stream — Interpreter thread first, then four
  parallel specialist threads, then assembly. The visible parallelism is the demo.
- **Monitor 2:** `field-guide.html` open in a browser; rotate the 3D beast live (and
  play the walk-cycle animation if the Animator has landed).

## V1 scope vs stretch

- **V1 (must work end-to-end):** Interpreter + Biologist + Habitat + Society + 3D
  Modeler → `field-guide.html` with an interactive 3D viewer.
- **V1 (parallel, independent):** Animator → 2.5D cutout `walk-cycle.html` in the
  `{{video}}` slot. Promoted out of stretch: it no longer depends on the 3D Modeler,
  so it carries no schedule risk for the rest of the swarm. If it doesn't land, the
  coordinator omits the slot exactly as before.

## Out of scope

- External generative-AI APIs for 3D, video, or image inpainting (procedural only).
  The Animator fills occlusion gaps by overlapping part polygons at their joints, and
  classically (OpenCV Telea / local color sampling) where a real hole remains.
- Local-orchestration fallback (committed to managed-agents preview).
- Any presentation format other than the single HTML field-guide page.
