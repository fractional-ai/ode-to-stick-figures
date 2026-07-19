"""Create the Field Interpreter + four specialist sub-agents.

Saves agent IDs to .specialist_ids.json for upload_skills.py and
create_coordinator.py.
"""

import json
from pathlib import Path

from agents.definitions import INTERPRETER, SPECIALISTS
from lib.client import managed_client

META = {"track": "creature-swarm"}


def _create(client, spec):
    agent = client.beta.agents.create(
        name=spec["name"],
        model=spec["model"],
        system=spec["system"],
        tools=[{"type": "agent_toolset_20260401"}],
        metadata={**META, "role": spec["key"]},
    )
    print(f"  Created {spec['name']:32s} -> {agent.id}")
    return agent.id


def main() -> None:
    client = managed_client()
    ids = {}
    for spec in [INTERPRETER, *SPECIALISTS]:
        ids[spec["key"]] = _create(client, spec)
    Path(".specialist_ids.json").write_text(json.dumps(ids, indent=2))
    print(f"\nSaved {len(ids)} agent IDs to .specialist_ids.json")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
