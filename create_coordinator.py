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
from pathlib import Path

from agents.definitions import COORDINATOR_SYSTEM, MODELS
from lib.client import managed_client


def main() -> None:
    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    client = managed_client()

    coordinator = client.beta.agents.create(
        name="Creature Swarm Field Editor",
        model=MODELS["coordinator"],
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
