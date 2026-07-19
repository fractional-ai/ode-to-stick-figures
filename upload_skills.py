"""Upload each skill in skills/ and attach it to the matching specialist.

Idempotent: reuses a skill with the same display_title and skips a duplicate
attach. Handles retrieved skill entries whether the SDK returns dicts or model
objects (the original workshop repo assumed dicts and crashed on re-run).

Usage:
    uv run upload_skills.py
"""

import json
from pathlib import Path

from anthropic.lib import files_from_dir

from lib.client import managed_client

# skill directory -> specialist key. (folklore-society is owner's discretion; drop
# this line if that lane runs prompt-only.)
SKILL_TO_SPECIALIST = {
    "creature-biology": "biologist",
    "habitat-ecology": "habitat",
    "folklore-society": "society",
    "procedural-creature-3d": "modeler",
    # fieldguide-html attaches to the coordinator (see create_coordinator.py),
    # not a specialist, so it is uploaded there.
}


def _skill_id_of(entry):
    """Read skill_id from a dict or a model object."""
    if isinstance(entry, dict):
        return entry.get("skill_id")
    return getattr(entry, "skill_id", None)


def main() -> None:
    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    client = managed_client()

    existing_by_title = {}
    for skill in client.beta.skills.list(source="custom"):
        existing_by_title[skill.display_title] = skill.id

    uploaded = {}
    for skill_name, specialist_key in SKILL_TO_SPECIALIST.items():
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name} — no SKILL.md")
            continue

        title = skill_name.replace("-", " ").title()
        if title in existing_by_title:
            skill_id = existing_by_title[title]
            print(f"Reusing skill {skill_name} ({skill_id})")
        else:
            print(f"Uploading skill {skill_name}...")
            skill = client.beta.skills.create(
                display_title=title, files=files_from_dir(str(skill_dir))
            )
            skill_id = skill.id
            print(f"  -> {skill_id}")
        uploaded[skill_name] = skill_id

        specialist_id = specialist_ids[specialist_key]
        current = client.beta.agents.retrieve(specialist_id)
        current_skills = list(current.skills or [])
        if any(_skill_id_of(s) == skill_id for s in current_skills):
            print(f"  already attached to {specialist_key} ✓")
            continue
        new_skills = [
            {"type": "custom", "skill_id": _skill_id_of(s), "version": "latest"}
            for s in current_skills
        ] + [{"type": "custom", "skill_id": skill_id, "version": "latest"}]
        client.beta.agents.update(specialist_id, version=current.version, skills=new_skills)
        print(f"  attached to {specialist_key} ✓")

    Path(".skill_ids.json").write_text(json.dumps(uploaded, indent=2))
    print(f"\nUploaded/attached {len(uploaded)} skills.")
    print("Next: uv run create_coordinator.py")


if __name__ == "__main__":
    main()
