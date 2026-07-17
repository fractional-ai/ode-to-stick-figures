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
from pathlib import Path

from agents.definitions import INTERPRETER, SPECIALISTS
from lib.client import managed_client


# The Field Interpreter runs serially, first; the rest fan out in parallel.
# Both come from agents.definitions — the single source of truth for the roster.
ROSTER = [INTERPRETER, *SPECIALISTS]


def main() -> None:
    client = managed_client()

    specialist_ids: dict[str, str] = {}
    for spec in ROSTER:
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
