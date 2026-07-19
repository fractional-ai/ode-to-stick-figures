# Creature Spec contract

This folder holds the **Creature Spec** — the shared consistency contract for the
creature-swarm pipeline. It is the one structured object that makes every agent
describe the *same* made-up animal instead of drifting into five different creatures.

## What it is

A single JSON object emitted per doodle. Its shape is formalized in
[`creature-spec.schema.json`](./creature-spec.schema.json) (JSON Schema, draft
2020-12), with a worked, deliberately silly example in
[`creature-spec.example.json`](./creature-spec.example.json).

It has two halves:

- **Descriptive** — `name`, `distinctive_features`, `vibe` (plus loose reference to
  `parts`/`palette`). The text agents mine this.
- **Structural** — `body_plan`, `parts`, `palette`, `locomotion`. The 3D/animation
  agents treat this as literal build instructions.

## Who produces it

The **Field Interpreter** agent. It reads the doodle once (vision) and emits exactly
one Creature Spec. Nobody else writes one.

## Who consumes it

Everyone downstream:

- **Biologist**, **Habitat**, **Society** — text agents, each producing a markdown
  section keyed off the descriptive half.
- **3D Modeler** — composes primitives from `body_plan`/`parts`, tints from
  `palette`, exports `creature.glb`.
- **Animator** (stretch) — builds a parametric walk cycle from `parts`/`locomotion`.

## Why it's frozen

This is the consistency seam. Freezing it first is what lets each agent lane be
owned and built in parallel: once the shape is fixed, the Interpreter lane and every
consumer lane can proceed against the contract without waiting on each other. A
specialist that can't parse a Spec asks the coordinator for a re-brief rather than
inventing a divergent creature.

## Source of truth

The authoritative shape is defined in the approved design doc at
[`docs/superpowers/specs/2026-07-17-creature-swarm-design.md`](../docs/superpowers/specs/2026-07-17-creature-swarm-design.md),
section "Contract 1 — Creature Spec". This schema formalizes that section; if the two
ever disagree, the design doc wins until this contract is updated to match.
