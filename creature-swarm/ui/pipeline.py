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
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWARM = REPO / "creature-swarm"
SKILL = SWARM / "skills" / "walk-cycle-anim"
GUIDE = SWARM / "skills" / "fieldguide-html"
MODELER = SWARM / "skills" / "procedural-creature-3d"

for p in (SWARM, SKILL, GUIDE, MODELER):
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


def _read(path: Path):
    text = path.read_text()
    return json.loads(text) if path.suffix == ".json" else text


def cached(path: Path, produce, wait_s: float = 240.0):
    """Memoise one model call on disk, once, even across processes.

    Cache per API RESULT, not per finished page. Assembly is the fragile part and the
    model calls are the expensive part; caching only the final HTML means any late
    failure re-bills the whole swarm (it cost us a 50-second retry to learn that).
    With this, a broken assembly step re-runs for free and iteration is instant.

    The lock is not paranoia. `prewarm.py` and a browser hitting /guide race on exactly
    the same artifacts, and a bare exists()-then-write is check-then-act: both miss,
    both call, both pay. We claim the work with an O_EXCL marker; whoever loses waits
    for the winner's file instead of duplicating the call. A stale marker (killed
    process) expires so it can't wedge the pipeline forever.

    Delete the file to force a refetch.
    """
    if path.exists():
        return _read(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")

    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        # Someone else is already producing this. Wait for their result.
        age = time.time() - lock.stat().st_mtime if lock.exists() else 0
        if age < wait_s:
            deadline = time.time() + wait_s
            while time.time() < deadline:
                if path.exists():
                    return _read(path)
                time.sleep(0.5)
        # Winner died or took too long — steal the claim rather than wedge forever.
        lock.unlink(missing_ok=True)
        return cached(path, produce, wait_s)

    try:
        value = produce()
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(value, indent=2) if path.suffix == ".json" else value)
        tmp.replace(path)  # atomic: readers never see a half-written artifact
        return value
    finally:
        lock.unlink(missing_ok=True)


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


HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def as_palette(v) -> list[str]:
    """Coerce `palette` to the list of hex strings the schema promises.

    The schema says array-of-hex, and the Interpreter returns a NAMED DICT
    ({"body_fill": "#eef2f0", "outline": "#3d8b83"}) on 12 of our 13 real drawings —
    only one happened to comply. The 3D Modeler indexes palette[0], so it died with
    KeyError: 0 on almost every actual creature while its tests stayed green, because
    the test fixture is schema-conformant and nobody had fed it live output.

    Dict insertion order survives JSON parsing, so values() preserves the Interpreter's
    own "most dominant first" ordering. Coerced here rather than in build.py because
    that's another lane's file, and rather than by re-prompting because that would throw
    away every cached Spec. The root cause is the Interpreter ignoring its own contract.
    """
    if isinstance(v, dict):
        v = list(v.values())
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, (list, tuple)):
        return ["#cccccc"]
    out = [c for c in (str(x).strip() for x in v) if HEX.match(c)]
    return out or ["#cccccc"]


WORDS = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,
         "nine":9,"ten":10,"a pair":2,"pair":2,"several":4,"many":8,"lots":8,"numerous":8}


def as_count(v) -> int:
    """Coerce parts[].count to the int the schema promises.

    Same failure as `palette`: the schema says integer, the Interpreter writes prose
    ("many, in two rows"), and int() raises deep inside the 3D Modeler. A child's
    drawing genuinely invites "many" as an answer, so the model isn't being stupid —
    the contract just doesn't allow it. Read a leading number if there is one, fall back
    to a number word, else guess low rather than emit a hundred-legged mesh.
    """
    if isinstance(v, bool):
        return 1
    if isinstance(v, (int, float)):
        return max(0, min(int(v), 64))
    text = str(v).strip().lower()
    m = re.match(r"\d+", text)
    if m:
        return max(0, min(int(m.group()), 64))
    for word, n in WORDS.items():
        if word in text:
            return n
    return 2


def normalize_spec(spec: dict) -> dict:
    """Make a live Creature Spec actually match its schema before anyone consumes it.

    The Interpreter violates its own contract in ways its conformant test fixture never
    shows, and every downstream lane trusts the schema. One place to repair it.
    """
    spec["palette"] = as_palette(spec.get("palette"))
    parts = spec.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and "count" in part:
                part["count"] = as_count(part["count"])
    return spec


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


def anim_overrides(spec: dict, env: str, stem: str) -> dict:
    """The Spec-derived arguments the walk cycle is built with.

    Defined once because two callers build animations: this module, on the first run,
    and the gallery, when it rebuilds a stale one. When the gallery called bare
    build() instead, its rebuild silently dropped every one of these and the animation
    reverted to the rig's own defaults — a different name, palette and world than the
    card and the field guide were showing for the same creature.
    """
    return {
        "name": flat(spec.get("name")) or stem,
        "vibe": flat(spec.get("vibe")),
        "locomotion": flat(spec.get("locomotion")),
        "palette": spec["palette"],
        "environment": env,
    }


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
    # Normalise before anything consumes it. Every downstream lane assumes the schema.
    spec = normalize_spec(spec)

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

    # The 3D Modeler lane. Deterministic trimesh over the same Spec, so no API call and
    # nothing to cache against the model: if the file is missing we just rebuild it.
    # Without this every guide's Specimen section reads "3D model not available", which
    # is a whole specialist's output missing from the page.
    glb = cache / f"{stem}.glb"
    if not glb.exists():
        try:
            from build import build_creature_glb

            build_creature_glb(spec, str(glb))
        except Exception as e:
            print(f"  3D modeler failed for {stem}: {type(e).__name__}: {e}")

    anim = cache / f"{stem}.html"
    build(doodle, rig, anim, color=True, overrides=anim_overrides(spec, env, stem))

    html = render_field_guide(
        creature_name=flat(spec.get("name")) or stem,
        tagline=flat(spec.get("vibe")),
        doodle_path=str(doodle),
        biology_html=md_to_html(results.get("biologist", "_missing_")),
        habitat_html=md_to_html(results.get("habitat", "_missing_")),
        society_html=md_to_html(results.get("society", "_missing_")),
        glb_path=str(glb) if glb.exists() else None,
        # {{video}} takes the walk-cycle HTML and inlines it as a data-URI iframe
        # (render.py, post-#23) — not an .mp4. That keeps the guide a single portable
        # file instead of depending on this dev server being up.
        video_path=str(anim),
    )

    out = cache / f"{stem}.guide.html"
    out.write_text(html)
    return out
