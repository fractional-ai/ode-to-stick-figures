# Project Plan: Animal Encyclopedia (Multi-Agent)

> Source: team planning meeting, July 17, 2026 —
> [Granola notes](https://notes.granola.ai/t/d4a99333-80ce-4316-841c-ead6f4fca06e-009c2hma)
> · [meeting transcript chat](https://notes.granola.ai/t/07d62b97-5617-4c1e-9a65-92c070c30b7a)

We are repurposing this repo's coordinator + specialists + skills pattern (the
Deal Desk demo) to build an **animal encyclopedia** with a multi-agent system.
**Deadline: 4pm today (July 17, 2026).**

## Project concept

- Multi-agent system that produces an animal encyclopedia.
- Agents cover distinct areas:
  - Encyclopedia / description writing
  - Habitat and botany-level content
  - Image generation (artists involved)
  - 3D modeling or animation
- 3D modeling complexity is unknown; 2D image animation is the simpler
  fallback if 3D doesn't pan out.
- Art style idea: hand-drawn sharpie on paper, scanned and uploaded.

## Agent orchestration structure

- 5–10 agents, each doing continuously interesting tasks.
- One coordinator agent oversees the swarm and presents the output
  (same shape as `create_coordinator.py` / `create_specialists.py` here).
- **Each team member builds one independent agent**, forked into the
  Fractional AI repo.
- Pipelining is allowed: e.g. the biologist agent feeds into the
  animation agent.
- Meta-agent idea: scan the 133 forks of a relevant repo to surface good ideas.

## Evals

- Deterministic checks preferred wherever possible — 5–10 identified as
  feasible.
- LLM-as-judge floated for the evals that can't be deterministic.
- Open question: do evals strictly need to be event-based?

## Open questions

- Finalize orchestration design and agent roles.
- How do we get an agent to produce a 3D model or animation by the deadline?
- API key scope: development use only, or repo-based agent execution too?

## Action items

- [ ] **Set up fork in Fractional AI repo** — each person assigns themselves
  one agent; all work lives in the shared repo.
- [ ] **Determine 3D modeling or animation approach** — unresolved; must land
  by the 4pm deadline or fall back to 2D animation.
- [ ] **Clarify API key scope** — confirm whether the key is for development
  use or repo-based agent execution only.
