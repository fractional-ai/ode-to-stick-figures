# Biologist & Habitat Skills — Kid-Friendly, Real-Animal-Grounded — Design

**Date:** 2026-07-17
**Status:** Approved
**Base:** Root flat pattern (`create_specialists.py`, `upload_skills.py`, `skills/`) — the
already-merged, self-contained repurpose of the Deal Desk workshop scripts for
Creature Swarm (see `docs/superpowers/specs/2026-07-17-creature-swarm-design.md`).

## Context

Two parallel, unreconciled implementations of Creature Swarm exist in this repo:

1. **Root flat pattern** — `create_specialists.py`, `create_coordinator.py`,
   `upload_skills.py`, `schemas/creature-spec.schema.json`, `skills/*/SKILL.md`.
   Already has a working, wired-up Biologist and Habitat agent + skill.
2. **`creature-swarm/` subfolder pattern** — matches the formal design/plan docs,
   has `lib/`, `agents/definitions.py`, a test suite, and a stricter/diverged
   Creature Spec schema. Missing a `creature-biology` skill entirely.

This work targets **only the root flat pattern**. The `creature-swarm/` subfolder
is left untouched.

## Problem

The existing `skills/creature-biology/SKILL.md` and `skills/habitat-ecology/SKILL.md`
(and their matching system prompts in `create_specialists.py`) produce deadpan,
adult-register field-guide prose (mock-Latin binomials, "TAXONOMY / ANATOMY / DIET
/ ADAPTATIONS" blocks). Two things are missing for this project's actual audience
and goal:

- **No real-animal grounding.** The skills reason purely from the Creature Spec's
  abstract fields (`body_plan`, `parts`, `locomotion`) without ever connecting a
  trait back to how a real animal actually solves the same problem.
- **Not written for children.** Structure and vocabulary assume an adult reader
  comfortable with taxonomic Latin and ecological jargon.

## Design

### Biologist (`skills/creature-biology/SKILL.md` + `create_specialists.py` biologist entry)

- **Research step (new):** before writing, use the agent's web_search/web_fetch
  tools (already granted via `agent_toolset_20260401`) to identify 1-2 real
  animals whose real biology plausibly explains a notable trait in the spec —
  e.g., six legs + broad feet → look up how a real many-legged or broad-footed
  animal distributes weight — and pull one genuine fact to ground the comparison.
  Keep the existing anatomy/diet inference tables (leg-count → gait framing,
  anatomical signal → diet) as the reasoning scaffold; the research step
  supplies the concrete real-world anchor, it doesn't replace the scaffold.
- **Output rewrite:** replace the `TAXONOMY / ANATOMY / DIET / ADAPTATIONS` block
  with a kid-friendly structure — short sentences, concrete comparisons kids can
  picture (sizes vs. familiar objects), a "Real Animals It's Like" callout citing
  what's real vs. invented, and jargon explained in the same sentence it's used.
- **Invariant kept:** treat the Creature Spec as ground truth; never contradict it.
- **System prompt update:** the `biologist` entry in `create_specialists.py`
  explicitly names the research step and the child audience.

### Habitat (`skills/habitat-ecology/SKILL.md` + `create_specialists.py` habitat entry)

Same treatment, mirrored onto habitat/ecology content:

- **Research step (new):** look up a real biome and 1-2 real animals that
  actually live the way the spec's `locomotion` implies, to ground the invented
  range/biome choice. Keep the existing locomotion→biome compatibility table and
  food-web niche table as the reasoning scaffold.
- **Output rewrite:** replace `RANGE / BIOME & CLIMATE / ECOLOGICAL NICHE` with a
  kid-friendly narrative structure, same tone rules as Biologist (concrete
  comparisons, explained jargon, a real-animal callout).
- **Invariant kept:** treat the spec as ground truth; keep the inconsistency-flagging
  behavior (e.g. `float` locomotion vs. large land-bound size) but phrase the flag
  in kid-friendly terms too.
- **System prompt update:** mirrors the Biologist's — research step + child
  audience named explicitly.

### No changes needed elsewhere

`upload_skills.py`'s `SKILL_TO_SPECIALIST` mapping already routes
`creature-biology` → `biologist` and `habitat-ecology` → `habitat`. Schema,
coordinator, and the Field Interpreter are untouched.

## Testing

The root flat pattern has no unit-test harness — it's the live-run workshop
style. Verification:

1. Run `setup_environment.py` → `create_specialists.py` → `upload_skills.py`
   against a real `ANTHROPIC_API_KEY` (managed-agents preview), if available in
   this environment.
2. Send the fixture spec at `creature-swarm/contracts/creature-spec.example.json`
   to the Biologist and Habitat agents in their own standalone sessions
   (bypassing the coordinator), and read back the replies to confirm tone and
   real-animal grounding land as intended.
3. If live API access isn't available, verify statically (frontmatter present,
   `SKILL_TO_SPECIALIST` wiring correct, prompts read as intended) and flag live
   verification as outstanding.

## Out of scope

- Reconciling the root flat pattern with the `creature-swarm/` subfolder pattern.
- Society, 3D Modeler, coordinator, or fieldguide-html changes.
