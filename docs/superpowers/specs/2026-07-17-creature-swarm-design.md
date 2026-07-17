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
      ┌─────────────┼─────────────┬──────────────┐
      ▼             ▼             ▼              ▼
 ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐
 │Biologist│  │ Habitat  │  │ Society  │  │3D Modeler │
 └─────────┘  └──────────┘  └──────────┘  └───────────┘
                                                │ creature.glb
                                          ┌───────────┐  (stretch, runs
                                          │  Animator │   after 3D returns)
                                          └───────────┘  → walk-cycle.mp4
```

- **Phase 1 (serial):** Coordinator delegates to the Field Interpreter, which reads
  the doodle once and emits the canonical **Creature Spec**.
- **Phase 2 (parallel):** Coordinator fans the Spec out to Biologist, Habitat,
  Society, and 3D Modeler simultaneously.
- **Phase 3 (assemble):** Coordinator runs the `fieldguide-html` skill to stitch all
  outputs into one portable HTML page.
- **Stretch:** The Animator joins the roster and runs *after* the 3D Modeler returns
  (it depends on the model/rig).

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
| **Animator** (stretch) | sonnet | `walk-cycle-anim` (stub) | Spec + `.glb` | `walk-cycle.mp4` |
| **Coordinator** | opus | `fieldguide-html` | all of the above | `field-guide.html` |

Each agent is an independently ownable lane. The two shared files to **freeze first**
are the Creature Spec schema and the `fieldguide-html` slot contract.

## Contract 1 — Creature Spec (consistency seam)

The Interpreter emits one structured JSON that every downstream agent keys off, so
all agents describe the *same* creature. Text agents mine the descriptive half; the
3D/video agents treat the structural half as literal build instructions.

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
- **Structural consumers** (3D/Animator): `body_plan`, `parts`, `palette`,
  `locomotion` as build parameters.

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
- `{{video}}` — `<video>` block; omitted if the stretch isn't built

## Procedural media approach

- **3D:** Python `trimesh` in the sandbox composes primitives (spheres, capsules,
  cylinders) from `body_plan`/`parts`, colors them from `palette`, exports
  `creature.glb`. Deliberately lumpy — a serious pipeline producing a
  crayon-faithful blob.
- **Video (stretch):** reuse the same primitive assembly, apply a simple parametric
  walk cycle (per-leg phase offsets), render N frames offscreen → `ffmpeg` →
  `walk-cycle.mp4`. Depends on `parts`/`locomotion`; can rebuild from Spec even if it
  also loads the `.glb`.

## Repo structure

New self-contained folder alongside the existing workshop options, mirroring their
file conventions:

```
creature-swarm/
  README.md
  requirements.txt          (anthropic, python-dotenv, trimesh, ffmpeg-python)
  create_specialists.py     (Interpreter + 4 specialists [+ Animator stretch])
  create_coordinator.py
  upload_skills.py
  setup_environment.py       (included from the start — original repo orphaned this)
  run_creature_swarm.py      (upload doodle, stream events, download page + media)
  download_deliverable.py
  skills/
    creature-biology/SKILL.md
    habitat-ecology/SKILL.md
    folklore-society/SKILL.md          (owner's discretion: prompt-only or skill)
    procedural-creature-3d/SKILL.md
    fieldguide-html/SKILL.md           (+ template.html)
    walk-cycle-anim/SKILL.md           (STUB — clear handoff contract, see below)
  synthetic-data/
    doodle-example.png                 (sample bad drawing to demo with)
```

## Team split

Natural ownership lanes: one person per specialist+skill pair; one owns the
Interpreter + Spec schema; one owns the `fieldguide-html` template + coordinator
assembly. The Spec schema and slot contract are frozen first so lanes proceed in
parallel.

The `walk-cycle-anim` skill ships as a **stub** intended to be completed by a
separate person driving their own Claude Code instance. The stub must state its full
contract so it can be picked up cold: input = Creature Spec + `creature.glb`, output =
`walk-cycle.mp4`, and it fills the `{{video}}` slot. No working animation code in V1.

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
  play the walk-cycle video if the stretch is built).

## V1 scope vs stretch

- **V1 (must work end-to-end):** Interpreter + Biologist + Habitat + Society + 3D
  Modeler → `field-guide.html` with an interactive 3D viewer.
- **Stretch:** Animator → `walk-cycle.mp4` embedded in the page (reuses the 3D rig).

## Out of scope

- External generative-AI APIs for 3D or video (procedural only).
- Local-orchestration fallback (committed to managed-agents preview).
- Any presentation format other than the single HTML field-guide page.
