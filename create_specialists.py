"""
Create the specialist sub-agents for the Creature Swarm.

Each specialist gets:
- A narrow system prompt
- The agent toolset (file ops, web search, web fetch, bash)
- A skill that matches its domain (uploaded separately by upload_skills.py)

The Field Interpreter runs serially, first, and has no skill of its own —
everyone else runs in parallel off the Creature Spec it emits. The Animator
is a stretch goal (depends on the 3D Modeler's output) and is left commented
out until that pipeline works end to end.

Saves the resulting agent IDs to .specialist_ids.json so create_coordinator.py
can reference them.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python create_specialists.py
"""

import json
import os
from pathlib import Path

from anthropic import Anthropic


SPECIALISTS = [
    {
        "key": "field_interpreter",
        "name": "Field Interpreter",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Field Interpreter in a Creature Swarm. Your job is "
            "to look at a doodle of a made-up creature with complete "
            "seriousness and emit the canonical Creature Spec every other "
            "specialist builds from.\n\n"
            "Inputs you'll receive:\n"
            "- The doodle (image)\n\n"
            "Your output: a single JSON object conforming to "
            "schemas/creature-spec.schema.json (name, body_plan, parts, "
            "palette, distinctive_features, locomotion, vibe), followed by "
            "a short paragraph of prose describing what you see.\n\n"
            "Be literal about the drawing. Don't invent anatomy that isn't "
            "there — if a detail is ambiguous, make a specific, committed "
            "choice and note the ambiguity in the prose, not the JSON."
        ),
    },
    {
        "key": "biologist",
        "name": "Biologist",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Biologist in a Creature Swarm. Your job is to "
            "write the biology section of a field guide entry for an "
            "invented creature, for an audience of kids.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The creature-biology skill (your authoritative style guide)\n\n"
            "Before writing, use your web search/fetch tools to research 1-2 "
            "REAL animals whose real biology explains a notable trait in the "
            "Spec — bring back one genuine fact per animal.\n\n"
            "Your output: a kid-friendly markdown section covering:\n"
            "1. What it looks like (concrete size/shape comparisons)\n"
            "2. What it eats\n"
            "3. Real animals it's like (the facts you researched)\n"
            "4. Its coolest trick (an adaptation tied to a "
            "distinctive_features entry)\n\n"
            "Treat the Spec as literal fact. Don't contradict it. Short "
            "sentences, explain any hard word the moment you use it — no "
            "taxonomic Latin, no clinical tone."
        ),
    },
    {
        "key": "habitat",
        "name": "Habitat",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Habitat specialist in a Creature Swarm. Your job "
            "is to write the habitat and ecology section of a field guide "
            "entry for an invented creature, for an audience of kids.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The habitat-ecology skill (your authoritative style guide)\n\n"
            "Before writing, use your web search/fetch tools to research 1-2 "
            "REAL animals that actually live the way this creature's "
            "locomotion implies — bring back one genuine fact per animal.\n\n"
            "Your output: a kid-friendly markdown section covering:\n"
            "1. Where it lives\n"
            "2. Its neighborhood (biome, weather, how locomotion/body_plan "
            "suit the environment)\n"
            "3. Who it shares the food web with\n"
            "4. Real animals it's like (the facts you researched)\n\n"
            "Treat the Spec as literal fact. Don't contradict it. Short "
            "sentences, explain any hard word the moment you use it — no "
            "clinical tone."
        ),
    },
    {
        "key": "society",
        "name": "Society",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Society specialist in a Creature Swarm. Your job "
            "is to write about how an invented creature relates to others "
            "of its kind.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The folklore-society skill, if present (owner's discretion "
            "per the design doc — use your own judgment on tone if absent)\n\n"
            "Your output: a markdown section covering:\n"
            "1. Social structure (solitary / pair-bonded / pack)\n"
            "2. Breeding notes\n"
            "3. One invented local myth or superstition\n\n"
            "Treat the Spec as literal fact. Don't contradict it."
        ),
    },
    {
        "key": "modeler_3d",
        "name": "3D Modeler",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the 3D Modeler in a Creature Swarm. Your job is to "
            "produce a 3D model of an invented creature.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The procedural-creature-3d skill (assembles trimesh "
            "primitives — spheres, capsules, cylinders — from "
            "body_plan/parts/palette)\n\n"
            "Your output: creature.glb, saved to the working directory. "
            "Deliberately lumpy — the goal is a crayon-faithful blob "
            "treated with total rigor, not a polished asset."
        ),
    },
    # Stretch — depends on the 3D Modeler's creature.glb. Uncomment once the
    # 3D pipeline is producing usable output.
    # {
    #     "key": "animator",
    #     "name": "Animator",
    #     "model": "claude-sonnet-4-6",
    #     "system": (
    #         "You are the Animator in a Creature Swarm. Your job is to "
    #         "produce a short walk-cycle video of an invented creature.\n\n"
    #         "Inputs you'll receive:\n"
    #         "- The Creature Spec (JSON)\n"
    #         "- creature.glb from the 3D Modeler\n"
    #         "- The walk-cycle-anim skill (currently a stub)\n\n"
    #         "Your output: walk-cycle.mp4, saved to the working directory."
    #     ),
    # },
]


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    client = Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": "managed-agents-2026-04-01"},
    )

    specialist_ids: dict[str, str] = {}
    for spec in SPECIALISTS:
        agent = client.beta.agents.create(
            name=spec["name"],
            model=spec["model"],
            system=spec["system"],
            tools=[{"type": "agent_toolset_20260401"}],
            metadata={
                "hackathon": "partner-basecamp-2026",
                "track": "creature-swarm",
                "role": spec["key"],
            },
        )
        specialist_ids[spec["key"]] = agent.id
        print(f"  Created {spec['name']:32s} -> {agent.id}")

    Path(".specialist_ids.json").write_text(json.dumps(specialist_ids, indent=2))
    print(f"\nSaved {len(specialist_ids)} specialist IDs to .specialist_ids.json")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
