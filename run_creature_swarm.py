"""
Run the Creature Swarm against a doodle image.

Uploads the doodle as a base64 image content block (simpler than the Files
API for hackathon-scale content). Streams events as they come in: watch for
the Field Interpreter thread first (serial), then the specialist threads
spawning together (parallel), then the coordinator assembling the page.

Saves the final transcript and downloaded deliverables to outputs/.

Usage:
    python run_creature_swarm.py [path/to/doodle]
"""

import base64
import mimetypes
import os
import sys
from pathlib import Path

from anthropic import Anthropic


DEFAULT_DOODLE = Path("examples/drawings/shark-dog.webp")
OUTPUT_DIR = Path("outputs")


def load_doodle_as_image_block(path: Path) -> dict:
    media_type, _ = mimetypes.guess_type(str(path))
    if media_type is None:
        raise SystemExit(f"Could not determine media type for {path}")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    if not Path(".coordinator_id").exists() or not Path(".environment_id").exists():
        raise SystemExit(
            "Missing .coordinator_id or .environment_id. Run "
            "create_specialists.py, create_coordinator.py, upload_skills.py, "
            "and setup_environment.py first."
        )

    doodle_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOODLE
    if not doodle_path.exists():
        raise SystemExit(f"Doodle not found: {doodle_path}")

    coordinator_id = Path(".coordinator_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()

    client = Anthropic()

    print(f"Loading doodle: {doodle_path}")
    image_block = load_doodle_as_image_block(doodle_path)

    print(f"\nStarting session against coordinator {coordinator_id}...")
    session = client.beta.sessions.create(
        agent=coordinator_id,
        environment_id=environment_id,
        title=f"Creature Swarm — {doodle_path.name}",
    )
    Path(".last_session_id").write_text(session.id)

    user_message = {
        "type": "user.message",
        "content": [
            {
                "type": "text",
                "text": (
                    "A doodle has arrived. Run the standard process:\n"
                    "1. Delegate to the Field Interpreter alone first — wait "
                    "for the Creature Spec.\n"
                    "2. Fan out to Biologist, Habitat, Society, and 3D "
                    "Modeler in parallel, in one message.\n"
                    "3. Assemble the field guide with the fieldguide-html "
                    "skill.\n\n"
                    "Treat the subject with complete scientific seriousness."
                ),
            },
            image_block,
        ],
    }

    # Stream the events — this is the demo. Watch for the serial Interpreter
    # pass followed by the parallel specialist fan-out.
    print("\n=== EVENT STREAM (this is the demo) ===\n")
    final_text_parts: list[str] = []

    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[user_message])
        for event in stream:
            t = event.type
            if t == "session.thread_created":
                print(f"  [thread spawned]   {event.agent_name}", flush=True)
            elif t == "session.thread_status_running":
                name = getattr(event, "agent_name", "?")
                print(f"  [thread running]   {name}", flush=True)
            elif t == "agent.thread_message_received":
                print(f"  [reply ←]          {event.from_agent_name}", flush=True)
            elif t == "agent.thread_message_sent":
                print(f"  [delegate →]       {event.to_agent_name}", flush=True)
            elif t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        final_text_parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif t == "agent.tool_use":
                print(f"\n  [tool: {getattr(event, 'name', '?')}]", flush=True)
            elif t == "session.status_idle":
                print("\n\n[swarm finished]")
                break

    OUTPUT_DIR.mkdir(exist_ok=True)
    transcript_path = OUTPUT_DIR / "coordinator-transcript.txt"
    transcript_path.write_text("".join(final_text_parts))
    print(f"\nCoordinator transcript saved to {transcript_path}")

    # Pull every file the agents produced in the container
    print("\nDownloading deliverables from the session container...")
    files = client.beta.files.list(
        scope_id=session.id,
        betas=["managed-agents-2026-04-01"],
    )
    file_count = 0
    for f in files.data:
        out_path = OUTPUT_DIR / f.filename
        print(f"  {f.filename}  ->  {out_path}")
        content = client.beta.files.download(f.id)
        content.write_to_file(str(out_path))
        file_count += 1

    if file_count == 0:
        print("  (no files found — agents may have produced text-only output)")
    else:
        print(f"\nDownloaded {file_count} file(s) to {OUTPUT_DIR}/")

    print(f"\nView the full session (including all sub-agent threads) at:")
    print(f"  https://platform.claude.com/sessions/{session.id}")


if __name__ == "__main__":
    main()
