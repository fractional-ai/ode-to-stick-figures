# Example field guide — sharpie bird

A full, self-contained field-guide page generated end-to-end from a single
drawing: [`examples/drawings/sharpie-bird.jpg`](../../drawings/sharpie-bird.jpg).

Open [`field-guide.html`](./field-guide.html) in a browser. It's one portable
file — the doodle, the three specialist write-ups, and the walking animation are
all inlined, no server or network needed.

## What's here

| File | What it is |
| --- | --- |
| `field-guide.html` | The deliverable: creature name + tagline, biology/habitat/society sections, the original doodle, and the walk-cycle animation embedded live. |
| `walk-cycle.html` | The animation on its own — the drawing cut into a 2.5D puppet and walked. Embedded in `field-guide.html` as an iframe. |
| `sharpie-bird.rig.json` | The rig the vision pass authored from the drawing (image-space polygons, pivots, parent hierarchy). A real AI-generated rig, useful as a reference next to the hand-authored fixtures in `skills/walk-cycle-anim/rigs/`. |

The interpreter named the specimen **Duckbill Jag-Wing (*Anatoserratus
alarazor*)**. The rigging pass reads the drawing independently, so its `name`
field differs — that's expected; they're separate passes over the same doodle.

## How it was made

The animation lane is the repo's own scripts, unchanged:

```bash
cd skills/walk-cycle-anim
uv run rig_from_image.py  ../../../examples/drawings/sharpie-bird.jpg -o sharpie-bird.rig.json
uv run build_walk_cycle.py ../../../examples/drawings/sharpie-bird.jpg --rig sharpie-bird.rig.json -o walk-cycle.html
```

The text sections and final page use the specialist agent prompts from
`agents/definitions.py` and the `fieldguide-html` renderer
(`skills/fieldguide-html/render.py`): the Field Interpreter turns
the drawing into a Creature Spec, the Biologist / Habitat Ecologist / Folklore &
Society specialists each write their section from that spec, and `render.py` fills
the template slots. There's no 3D lane, so that slot degrades gracefully.

This example was assembled by driving those prompts and the renderer directly
(Messages API), rather than through the managed-agents coordinator — the output
is the same field guide the swarm is meant to produce.
