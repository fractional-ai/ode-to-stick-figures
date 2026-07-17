"""
Upload each skill in skills/ via the Skills API and attach to the right
agent. Specialist skills attach to their matching specialist; fieldguide-html
attaches to the coordinator, since assembly is the coordinator's job alone.

Uses `files_from_dir` (from anthropic.lib) to package the skill directory.
Each skill bundle must contain a SKILL.md at its root with proper YAML
frontmatter (`name` and `description`).

Usage:
    python upload_skills.py
"""

import json
from pathlib import Path

from anthropic.lib import files_from_dir

from lib.client import managed_client


# Map skill directory name → specialist key that should get it.
# walk-cycle-anim is left out until the Animator stretch specialist is
# uncommented in create_specialists.py — it's a stub with no code yet.
SKILL_TO_SPECIALIST = {
    "creature-biology":       "biologist",
    "habitat-ecology":        "habitat",
    "folklore-society":       "society",
    "procedural-creature-3d": "modeler_3d",
}

# Skills that belong to the coordinator, not a specialist.
COORDINATOR_SKILLS = ["fieldguide-html"]


def main() -> None:
    specialist_ids_path = Path(".specialist_ids.json")
    if not specialist_ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(specialist_ids_path.read_text())

    coordinator_id_path = Path(".coordinator_id")
    coordinator_id = (
        coordinator_id_path.read_text().strip() if coordinator_id_path.exists() else None
    )

    client = managed_client()

    # List existing custom skills so we can detect and reuse any prior uploads.
    # Skills API enforces unique display_title, so retrying with the same title
    # would otherwise fail. Idempotent retry is essential for hackathon dev loops.
    print("Checking for existing skills...")
    existing_by_title: dict[str, str] = {}
    for page in client.beta.skills.list(source="custom"):
        existing_by_title[page.display_title] = page.id

    uploaded: dict[str, str] = {}

    def upload_or_reuse(skill_name: str) -> str | None:
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name} — no SKILL.md found")
            return None
        display_title = skill_name.replace("-", " ").title()
        if display_title in existing_by_title:
            skill_id = existing_by_title[display_title]
            print(f"Reusing existing skill: {skill_name} ({skill_id})")
            return skill_id
        print(f"Uploading skill: {skill_name}...")
        skill = client.beta.skills.create(
            display_title=display_title,
            files=files_from_dir(str(skill_dir)),
        )
        print(f"  -> {skill.id}")
        return skill.id

    def attach(agent_id: str, skill_id: str) -> None:
        current = client.beta.agents.retrieve(agent_id)
        # Avoid duplicate attachment on re-run
        already_attached = any(
            s.get("skill_id") == skill_id for s in (current.skills or [])
        )
        if already_attached:
            print(f"  already attached ✓ (skipping)")
            return
        new_skills = list(current.skills or []) + [
            {"type": "custom", "skill_id": skill_id, "version": "latest"}
        ]
        client.beta.agents.update(agent_id, version=current.version, skills=new_skills)
        print(f"  attached ✓")

    for skill_name, specialist_key in SKILL_TO_SPECIALIST.items():
        skill_id = upload_or_reuse(skill_name)
        if skill_id is None:
            continue
        uploaded[skill_name] = skill_id
        specialist_id = specialist_ids[specialist_key]
        print(f"  attaching to specialist `{specialist_key}` ({specialist_id})...")
        attach(specialist_id, skill_id)

    if coordinator_id:
        for skill_name in COORDINATOR_SKILLS:
            skill_id = upload_or_reuse(skill_name)
            if skill_id is None:
                continue
            uploaded[skill_name] = skill_id
            print(f"  attaching to coordinator ({coordinator_id})...")
            attach(coordinator_id, skill_id)
    else:
        print(
            "  .coordinator_id not found — run create_coordinator.py, then "
            "re-run this script to attach coordinator-only skills (fieldguide-html)."
        )

    Path(".skill_ids.json").write_text(json.dumps(uploaded, indent=2))
    print(f"\nUploaded {len(uploaded)} skills and attached them.")
    print("Next: python run_creature_swarm.py")


if __name__ == "__main__":
    main()
