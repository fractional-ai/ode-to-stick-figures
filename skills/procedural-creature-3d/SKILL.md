---
name: procedural-creature-3d
description: Build a creature.glb procedurally from a Creature Spec using trimesh primitives (spheres, capsules, cylinders), colored from the Spec's palette. Deliberately lumpy — a rigorous pipeline producing a crayon-faithful blob.
---

# Procedural Creature 3D

Use this skill to turn a Creature Spec into `creature.glb`.

## Approach

1. Parse `body_plan` — instantiate one primitive for the core:
   - `sphere` / `ovoid` -> `trimesh.creation.icosphere` (scaled for ovoid)
   - `slab` -> `trimesh.creation.box`
   - `cylinder` -> `trimesh.creation.cylinder`
2. For each entry in `parts`, attach `count` instances of a primitive
   (capsules for legs/tails, small spheres for eyestalks) at `placement`,
   scaled by `shape` heuristically. Exact placement is illustrative, not
   anatomically precise — the point is legible, not photoreal.
3. Apply `palette` as flat vertex colors — one color per part type is
   enough, no texturing.
4. Respect `symmetry`: bilateral parts get mirrored across the creature's
   long axis; radial parts get evenly distributed.
5. Merge into one mesh and export: `mesh.export("creature.glb")`.

## Non-negotiables

- Output must be literal to `body_plan`/`parts`/`palette` — no artistic
  liberties that contradict the Spec.
- Keep the primitive count low. This is meant to look assembled from
  building blocks, not sculpted.

## Testing standalone

This skill's code path should be runnable against a fixture Creature Spec
without spinning up the whole swarm — see the design doc's Testing section.

```bash
python -c "from build import build_from_spec; build_from_spec('fixtures/sample-spec.json')"
```

TODO (owner): write `build.py` implementing the above, plus
`fixtures/sample-spec.json` for standalone testing.
