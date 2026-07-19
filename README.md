# Ode to Stick Figures

Hand a child's drawing of a made-up animal to a swarm of agents and get back a
straight-faced field guide entry: the biology, the habitat, the folklore, and the
creature itself walking around.

The animation is the drawing's own pixels, not a reconstruction. We cut the paper
away, hinge the parts the child drew, and walk them. It stays recognisably theirs.

See [PLAN.md](PLAN.md) for the concept and agent roles.

## Run the gallery

```bash
cp .env.example .env      # add your ANTHROPIC_API_KEY
cd ui && ./serve.py       # http://127.0.0.1:8000
```

The scripts are [uv](https://docs.astral.sh/uv/) scripts with inline dependency
blocks, so `uv` fetches the interpreter and the deps on first run. Nothing to
install.

The example drawings ship with their animations and field guides already built and
checked in, so a fresh clone is all cache hits and costs no API calls. Drop a new
drawing on the gallery to run it through the swarm live.

One drawing has no animation on purpose. `snowmen-scene` is a painted scene with no
animal in it, and the gallery says so rather than animating paper slabs sliding
sideways. An honest refusal is a feature; plausible garbage is the worst thing we
could show.

## How it works

The **Field Interpreter** looks at the drawing once and emits a **Creature Spec**.
That Spec is the consistency seam: every other lane keys off it, so they all
describe the same animal rather than four different ones.

```
                        drawing
                           │
                  Field Interpreter (vision)
                           │
                    Creature Spec  ──────── contracts/creature-spec.schema.json
                           │
        ┌──────────┬───────┴───────┬──────────┐
   Biologist    Habitat        Society     Animator
        └──────────┴───────┬───────┴──────────┘
                           │
                     field guide page
```

The Spec is a frozen contract with real enums, validated in
`contracts/creature-spec.schema.json`.

## Layout

```
agents/definitions.py    the roster and every prompt, network-free and testable
contracts/               the Creature Spec schema + example (the frozen contract)
lib/                     shared Anthropic client, spec validation
skills/
├── walk-cycle-anim/     the 2.5D cutout animator: alpha-key, rigs, renderer
├── fieldguide-html/     assembles the page
├── creature-biology/    ─┐
├── habitat-ecology/      ├ the text lanes
├── folklore-society/    ─┘
└── procedural-creature-3d/
ui/                      the gallery: serve.py, pipeline.py, prewarm.py
evals/                   Creature Spec eval harness
examples/drawings/       the drawings, ordered easy to hard
tests/
```

## The animation, briefly

Flat parts cut from the drawing, hinged at joints, drawn on a canvas. Paper Mario,
or Monty Python's cutouts.

Two things carry it. First, the alpha-key has to remove the paper without eating
the child's linework, which is fussier than it sounds: white-balance the
photograph, derive the ink cutoff per image, close hard before filling, and never
open (opening erases thin pencil strokes). Second, every part polygon must overlap
into its parent past the pivot, so rotating it never reveals a gap — which is why
nothing needs inpainting.

Heading 0 faces left, the direction most kids draw. Turning sweeps through the
edge-on angle where the cutout goes flat and vanishes for a frame. That
flat-paper pivot is the charm; it isn't a bug to smooth out.

## Tests

```bash
pip install -r requirements.txt && pytest tests/
```
