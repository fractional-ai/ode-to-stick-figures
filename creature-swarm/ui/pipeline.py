"""Run the swarm for one drawing and assemble its field guide.

Interpreter (vision) -> Creature Spec, then Biologist / Habitat / Society fan out in
parallel off that Spec, and the Animator's walk cycle drops into the {{video}} slot.
Same topology and the same prompts as `agents/definitions.py` — this drives them with
plain `messages.create` rather than the managed-agents preview, because a local dev
server wants a synchronous call it can cache to disk, not a hosted run to poll.

The Spec is the consistency seam: the text lanes and the animation both key off it, so
they describe the same creature.
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWARM = REPO / "creature-swarm"
SKILL = SWARM / "skills" / "walk-cycle-anim"
GUIDE = SWARM / "skills" / "fieldguide-html"

for p in (SWARM, SKILL, GUIDE):
    sys.path.insert(0, str(p))

from agents.definitions import INTERPRETER, SPECIALISTS  # noqa: E402
from build_walk_cycle import build  # noqa: E402
from render import render_field_guide  # noqa: E402


def _client():
    import os

    from anthropic import Anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set (looked for a .env up the tree)")
    return Anthropic(api_key=key)


def load_env() -> bool:
    """Find a .env anywhere up the tree. The repo documents creature-swarm/.env."""
    import os

    from dotenv import load_dotenv

    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    here = Path(__file__).resolve()
    for d in [SWARM, REPO, *REPO.parents]:
        env = d / ".env"
        if env.is_file():
            load_dotenv(env)
            if os.environ.get("ANTHROPIC_API_KEY"):
                return True
    return False


def _text(msg) -> str:
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def cached(path: Path, produce):
    """Memoise one model call on disk.

    Cache per API RESULT, not per finished page. Assembly is the fragile part and the
    model calls are the expensive part; caching only the final HTML means any late
    failure re-bills the whole swarm (it cost us a 50-second retry to learn that).
    With this, a broken assembly step re-runs for free and iteration is instant.

    Delete the file to force a refetch; `rm -rf .cache` is a full reset.
    """
    if path.exists():
        text = path.read_text()
        return json.loads(text) if path.suffix == ".json" else text
    value = produce()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) if path.suffix == ".json" else value)
    return value


def _json_from(text: str) -> dict:
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def interpret(doodle: Path, keyed_b64: str) -> dict:
    """Vision pass -> Creature Spec. Sonnet, per the roster."""
    c = _client()
    msg = c.messages.create(
        model=INTERPRETER["model"],
        max_tokens=2000,
        system=INTERPRETER["system"],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": keyed_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is the alpha-keyed cutout of a child's drawing — the "
                            "paper is removed so you see only what they drew. Emit the "
                            "Creature Spec as JSON only, no prose."
                        ),
                    },
                ],
            }
        ],
    )
    return _json_from(_text(msg))


def specialist(agent: dict, spec: dict) -> tuple[str, str]:
    """One text lane. Returns (key, markdown)."""
    c = _client()
    msg = c.messages.create(
        model=agent["model"],
        max_tokens=1200,
        system=agent["system"],
        messages=[
            {
                "role": "user",
                "content": (
                    "Creature Spec:\n\n```json\n"
                    + json.dumps(spec, indent=2)
                    + "\n```\n\nWrite your section as markdown. No top-level heading — "
                    "the field guide supplies it. Treat this creature with complete, "
                    "unwavering scientific seriousness."
                ),
            }
        ],
    )
    return agent["key"], _text(msg)


def flat(v, sep: str = " ") -> str:
    """Coerce a Spec field to a plain string.

    The schema says `name` is a string, but a model handed a "common name + mock-Latin
    binomial" instruction will sometimes return {"common": ..., "latin": ...}, and the
    assembly step's html.escape() then blows up on a dict. Be liberal here rather than
    fail the whole guide over a shape nobody promised — the alternative is a 500 after
    50 seconds of model calls.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return sep.join(flat(x) for x in v.values() if x)
    if isinstance(v, (list, tuple)):
        return sep.join(flat(x) for x in v if x)
    return str(v)


def choose_environment(habitat_md: str, spec: dict) -> str:
    """Let the Habitat Ecologist's section pick the animation's world.

    The engine ships eight backgrounds; something has to choose. The Habitat lane has
    already reasoned about where this creature lives, so reusing its answer keeps the
    page coherent — the guide says tidepools and the creature walks on a beach, rather
    than every creature on the same strip of grass regardless of what we wrote about it.
    Haiku, because this is a 1-token classification over text we already have.
    """
    from build_walk_cycle import ENVIRONMENTS

    c = _client()
    msg = c.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8,
        system=(
            "Pick the single best background world for a creature, given its field-guide "
            "habitat section. Reply with EXACTLY one word from this list and nothing "
            f"else: {', '.join(ENVIRONMENTS)}"
        ),
        messages=[
            {
                "role": "user",
                "content": f"{flat(spec.get('name'))}\n\nHabitat section:\n{habitat_md[:2500]}",
            }
        ],
    )
    pick = _text(msg).strip().lower().strip(".")
    return pick if pick in ENVIRONMENTS else "meadow"


def md_to_html(md: str) -> str:
    try:
        import markdown

        return markdown.markdown(md, extensions=["extra"])
    except ImportError:
        return "".join(f"<p>{p.strip()}</p>" for p in md.split("\n\n") if p.strip())


def run(stem: str, doodle: Path, rig: Path, cache: Path) -> Path:
    """Full swarm for one drawing -> field-guide.html on disk.

    Order matters: Interpreter is serial (everyone keys off its Spec), then the three
    text lanes and the animation run concurrently.
    """
    import base64
    import io

    from PIL import Image

    from build_walk_cycle import key as key_fn

    def keyed_b64() -> str:
        keyed, _ = key_fn(Image.open(doodle))
        buf = io.BytesIO()
        keyed.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    # Phase 1 (serial): the Spec is the consistency seam — everyone keys off it.
    spec = cached(cache / f"{stem}.spec.json", lambda: interpret(doodle, keyed_b64()))

    # Phase 2 (parallel): three text lanes, each cached independently so one bad
    # response doesn't re-bill the other two.
    text_agents = [a for a in SPECIALISTS if a["key"] in ("biologist", "habitat", "society")]

    def lane(a: dict) -> tuple[str, str]:
        return a["key"], cached(
            cache / f"{stem}.{a['key']}.md", lambda: specialist(a, spec)[1]
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(lane, text_agents))

    # Animation: drive it from the Spec so the walk matches the described creature.
    # The Habitat lane picks the world; cached like any other model call.
    env = cached(
        cache / f"{stem}.environment.txt",
        lambda: choose_environment(results.get("habitat", ""), spec),
    ).strip()

    anim = cache / f"{stem}.html"
    palette = spec.get("palette")
    build(
        doodle,
        rig,
        anim,
        color=True,
        overrides={
            "name": flat(spec.get("name")) or stem,
            "vibe": flat(spec.get("vibe")),
            "locomotion": flat(spec.get("locomotion")),
            "palette": palette if isinstance(palette, list) else None,
            "environment": env,
        },
    )

    html = render_field_guide(
        creature_name=flat(spec.get("name")) or stem,
        tagline=flat(spec.get("vibe")),
        doodle_path=str(doodle),
        biology_html=md_to_html(results.get("biologist", "_missing_")),
        habitat_html=md_to_html(results.get("habitat", "_missing_")),
        society_html=md_to_html(results.get("society", "_missing_")),
        glb_path=None,
        # {{video}} takes the walk-cycle HTML and inlines it as a data-URI iframe
        # (render.py, post-#23) — not an .mp4. That keeps the guide a single portable
        # file instead of depending on this dev server being up.
        video_path=str(anim),
    )

    out = cache / f"{stem}.guide.html"
    out.write_text(html)
    return out
