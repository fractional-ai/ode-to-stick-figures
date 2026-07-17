"""Create the cloud Environment the creature-swarm session runs in.

Idempotent — reuses .environment_id if present. Part of the standard run order:
setup_environment -> create_specialists -> upload_skills -> create_coordinator ->
run_creature_swarm.
"""

from pathlib import Path

from lib.client import managed_client


def main() -> None:
    env_path = Path(".environment_id")
    if env_path.exists():
        print(f"Environment already exists: {env_path.read_text().strip()}")
        print("(remove .environment_id to provision a new one)")
        return

    client = managed_client()
    environment = client.beta.environments.create(
        name="creature-swarm-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    env_path.write_text(environment.id)
    print(f"Environment created: {environment.id}")
    print("Next: python create_specialists.py")


if __name__ == "__main__":
    main()
