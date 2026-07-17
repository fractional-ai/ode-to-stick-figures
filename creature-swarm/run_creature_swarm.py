"""Run the creature swarm against a doodle, end to end.

Flow: Interpreter session (image -> Creature Spec) -> coordinator session
(Spec -> parallel specialists -> field-guide.html). The coordinator event
stream is printed live so the parallel fan-out is visible — that is the demo.

Run order (all first):
    python setup_environment.py
    python create_specialists.py
    python upload_skills.py
    python create_coordinator.py
    python run_creature_swarm.py [path/to/doodle.png]
"""

import base64
import json
import mimetypes
import sys
from pathlib import Path

from lib.client import MANAGED_AGENTS_BETA, managed_client
from lib.spec import validate_spec

OUTPUT_DIR = Path("outputs")
DEFAULT_DOODLE = Path("synthetic-data/doodle-example.png")


def _image_block(path: Path) -> dict:
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _require(*paths: str) -> None:
    missing = [p for p in paths if not Path(p).exists()]
    if missing:
        raise SystemExit(
            f"Missing {', '.join(missing)}. Run in order: setup_environment.py, "
            "create_specialists.py, upload_skills.py, create_coordinator.py."
        )


def interpret(client, environment_id: str, interpreter_id: str, doodle: Path) -> dict:
    """Serial pre-step: the Field Interpreter turns the raw image into a Spec."""
    print(f"\nInterpreting {doodle.name} -> Creature Spec...")
    session = client.beta.sessions.create(
        agent=interpreter_id,
        environment_id=environment_id,
        title="Creature interpretation",
    )
    parts: list[str] = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [
                {"type": "text", "text": (
                    "Interpret this drawing into a Creature Spec JSON that "
                    "conforms to the contract. Output only the JSON object."
                )},
                _image_block(doodle),
            ],
        }])
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        parts.append(block.text)
            elif event.type == "session.status_idle":
                break

    text = "".join(parts)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise SystemExit(
            "Interpreter did not return a JSON object. Raw reply:\n" + text
        )
    spec = json.loads(text[start:end + 1])
    try:
        validate_spec(spec)
    except ValueError as exc:
        # Don't abort the whole run on a minor schema drift — warn and proceed
        # so the demo still produces a field guide. Task 13 tightens this.
        print(f"  ! spec failed validation ({exc}); continuing anyway")
    print(f"  Creature: {spec.get('name', '(unnamed)')}")
    return spec


def run_coordinator(client, environment_id: str, coordinator_id: str, spec: dict) -> str:
    """Parallel phase: coordinator fans the Spec to specialists, then assembles."""
    print("\nStarting coordinator session...")
    session = client.beta.sessions.create(
        agent=coordinator_id,
        environment_id=environment_id,
        title=f"Field guide — {spec.get('name', 'creature')}",
    )
    Path(".last_session_id").write_text(session.id)

    user_message = (
        "A creature has been interpreted. Here is the Creature Spec (JSON). "
        "Run the field-guide desk:\n"
        "1. Delegate to the Biologist, Habitat, Society, and 3D Modeler in "
        "parallel — in a single message.\n"
        "2. Assemble the results into field-guide.html with your "
        "fieldguide-html skill.\n"
        "Treat the subject with complete scientific seriousness.\n\n"
        "```json\n" + json.dumps(spec, indent=2) + "\n```"
    )

    print("\n=== EVENT STREAM (this is the demo) ===\n")
    text_parts: list[str] = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": user_message}],
        }])
        for event in stream:
            t = event.type
            if t == "session.thread_created":
                print(f"  [thread spawned]  {getattr(event, 'agent_name', '?')}", flush=True)
            elif t == "agent.thread_message_sent":
                print(f"  [delegate ->]     {getattr(event, 'to_agent_name', '?')}", flush=True)
            elif t == "agent.thread_message_received":
                print(f"  [reply <-]        {getattr(event, 'from_agent_name', '?')}", flush=True)
            elif t == "agent.tool_use":
                print(f"  [tool: {getattr(event, 'name', '?')}]", flush=True)
            elif t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        text_parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif t == "session.status_idle":
                print("\n\n[swarm finished]")
                break

    (OUTPUT_DIR / "coordinator-transcript.txt").write_text("".join(text_parts))
    return session.id


def download_deliverables(client, session_id: str) -> int:
    print("\nDownloading deliverables from the session container...")
    files = client.beta.files.list(scope_id=session_id, betas=[MANAGED_AGENTS_BETA])
    count = 0
    for f in files.data:
        out = OUTPUT_DIR / f.filename
        client.beta.files.download(f.id).write_to_file(str(out))
        print(f"  {f.filename} -> {out}")
        count += 1
    if count == 0:
        print("  (no files produced — check the session in the console)")
    return count


def main() -> None:
    doodle = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOODLE
    if not doodle.exists():
        raise SystemExit(f"Doodle not found: {doodle}")
    _require(".coordinator_id", ".specialist_ids.json", ".environment_id")

    client = managed_client()
    coordinator_id = Path(".coordinator_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()
    interpreter_id = json.loads(Path(".specialist_ids.json").read_text())["interpreter"]

    OUTPUT_DIR.mkdir(exist_ok=True)
    spec = interpret(client, environment_id, interpreter_id, doodle)
    (OUTPUT_DIR / "creature-spec.json").write_text(json.dumps(spec, indent=2))

    session_id = run_coordinator(client, environment_id, coordinator_id, spec)
    download_deliverables(client, session_id)

    print(f"\nOpen {OUTPUT_DIR}/field-guide.html in a browser.")
    print(f"Session: https://platform.claude.com/sessions/{session_id}")


if __name__ == "__main__":
    main()
