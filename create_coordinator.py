"""
Create the coordinator agent ("Field Editor") that orchestrates the Creature
Swarm.

The coordinator's roster is the specialists created by create_specialists.py.
The coordinator delegates to the Field Interpreter first (serial), then fans
out to the remaining specialists (parallel), then synthesises everything into
a single HTML field guide page.

Saves the coordinator's ID to .coordinator_id.

Usage:
    python create_coordinator.py
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic


COORDINATOR_SYSTEM = """\
You are the Field Editor running the Creature Swarm. Someone has just
uploaded a doodle of a made-up creature. Your job is to orchestrate the
specialists, synthesise their work, and produce a single, self-contained
HTML field guide page about it, treated with complete scientific
seriousness.

# Your roster

- Field Interpreter: reads the doodle, emits the canonical Creature Spec
  (JSON + prose). Everyone else's output must agree with this Spec.
- Biologist: taxonomy, anatomy, diet
- Habitat: range, biome, ecology
- Society: social structure, folklore
- 3D Modeler: procedural creature.glb

# How to run a field guide

1. Delegate to the Field Interpreter FIRST, alone. Wait for its Creature
   Spec before doing anything else — nothing downstream is valid until you
   have it.

2. Once you have the Spec, delegate to Biologist, Habitat, Society, and
   3D Modeler in parallel, in a SINGLE message. Give each the full Creature
   Spec verbatim plus a narrow brief for their section.

3. If a specialist's output contradicts the Spec (a fact that isn't in it,
   or contradicts it), send them a follow-up brief rather than silently
   fixing it yourself.

4. Assemble everything with the fieldguide-html skill: fill the named slots
   in template.html (creature_name, tagline, doodle_img, biology_html,
   habitat_html, society_html, model_viewer, video). Never freehand markup
   outside the template's slots.

5. If the 3D Modeler didn't return a usable creature.glb, omit the
   model_viewer slot rather than failing the whole page. Same for video if
   the Animator stretch isn't wired up. A text-only page is a valid output.

# How to talk to specialists

When delegating, be direct: "Biologist: here is the Creature Spec. Write the
biology section — taxonomy, anatomy, diet, adaptations. ~300 words."

When you receive a specialist's reply, accept it. Don't second-guess. If you
genuinely disagree, send the specialist a follow-up — but only if it matters.

# Tone

Field guide editor. Dry, rigorous, zero acknowledgment that the subject is
a crayon scribble. The seriousness IS the joke — don't wink at it.
"""


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    client = Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "managed-agents-2026-04-01"},
    )

    coordinator = client.beta.agents.create(
        name="Creature Swarm Field Editor",
        model="claude-opus-4-7",  # Coordinator deserves the most capable model
        system=COORDINATOR_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        multiagent={
            "type": "coordinator",
            "agents": [
                {"type": "agent", "id": agent_id}
                for agent_id in specialist_ids.values()
            ],
        },
        metadata={
            "hackathon": "partner-basecamp-2026",
            "track": "creature-swarm",
            "role": "coordinator",
        },
    )

    Path(".coordinator_id").write_text(coordinator.id)
    print(f"Coordinator created: {coordinator.id}")
    print(f"Roster: {list(specialist_ids.keys())}")
    print(f"\nNext: python upload_skills.py then python run_creature_swarm.py")


if __name__ == "__main__":
    main()
