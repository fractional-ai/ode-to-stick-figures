"""Create the coordinator ("Field Editor") whose roster is the four specialists.

Also uploads + attaches the fieldguide-html skill to the coordinator, since the
coordinator owns final assembly. The interpreter is NOT in the coordinator's
roster — it runs as a pre-step in run_creature_swarm.py (it needs the raw image).
"""

import json
from pathlib import Path

from anthropic.lib import files_from_dir

from agents.definitions import COORDINATOR_SYSTEM, MODELS
from lib.client import managed_client

SPECIALIST_ROSTER_KEYS = ["biologist", "habitat", "society", "modeler"]


def main() -> None:
    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    client = managed_client()

    # Upload + attach fieldguide-html to the coordinator.
    fg_dir = Path("skills/fieldguide-html")
    fg_skill = client.beta.skills.create(
        display_title="Fieldguide Html", files=files_from_dir(str(fg_dir))
    )

    roster = [{"type": "agent", "id": specialist_ids[k]} for k in SPECIALIST_ROSTER_KEYS]
    coordinator = client.beta.agents.create(
        name="Creature Field Editor",
        model=MODELS["coordinator"],
        system=COORDINATOR_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        skills=[{"type": "custom", "skill_id": fg_skill.id, "version": "latest"}],
        multiagent={"type": "coordinator", "agents": roster},
        metadata={"track": "creature-swarm", "role": "coordinator"},
    )
    Path(".coordinator_id").write_text(coordinator.id)
    print(f"Coordinator created: {coordinator.id}")
    print(f"Roster: {SPECIALIST_ROSTER_KEYS}")
    print("Next: uv run setup_environment.py (if not done). Driving the coordinator is manual;")
    print("see the managed-agents section of the README.")


if __name__ == "__main__":
    main()
