from agents import definitions as d


def test_specialists_have_required_keys():
    keys = {s["key"] for s in d.SPECIALISTS}
    assert {"biologist", "habitat", "society", "modeler"} <= keys
    for s in d.SPECIALISTS:
        assert s["name"] and s["model"] and s["system"]


def test_interpreter_defined():
    assert d.INTERPRETER["key"] == "interpreter"
    assert "spec" in d.INTERPRETER["system"].lower()


def test_interpreter_prompt_demands_literal_transcription():
    system = d.INTERPRETER["system"].lower()
    # The governing rule: transcribe what's actually drawn, don't genericize it away.
    assert "literal" in system
    assert "shark" in system and "dog" in system  # the canonical example case
    # Never bail on weird/ambiguous input — always produce a full spec.
    assert "never refuse" in system or "always commit" in system


def test_coordinator_prompt_mentions_all_lanes():
    text = d.COORDINATOR_SYSTEM.lower()
    for word in ("biolog", "habitat", "society", "3d", "field-guide"):
        assert word in text


# --- the gait dispatch -------------------------------------------------------
# These check contracts that span two files and can silently drift, which is what
# happened here: the renderer implemented a gait the schema couldn't ask for, the
# schema offered five the renderer had never heard of, and every committed Spec
# carried prose that matched none of them.

import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _implemented_gaits() -> set[str]:
    template = (REPO / "skills" / "walk-cycle-anim" / "template.html").read_text()
    return set(re.findall(r"(\w+):", re.search(r"const BASE = \{([^}]*)\}", template).group(1)))


def test_every_locomotion_the_spec_allows_resolves_to_a_real_animation_model():
    """`locomotion` is a dispatch key into gait models in template.html, matched
    exactly. A value the renderer doesn't implement doesn't fail — it falls through to
    the `??` defaults and comes out as an ordinary walk."""
    schema = json.loads((REPO / "contracts" / "creature-spec.schema.json").read_text())
    allowed = schema["properties"]["locomotion"]["enum"]

    template = (REPO / "skills" / "walk-cycle-anim" / "template.html").read_text()
    aliases = set(
        re.findall(r"(\w+):", re.search(r"const LOCO_MODEL = \{([^}]*)\}", template).group(1))
    )
    implemented = _implemented_gaits()

    unreachable = [v for v in allowed if v not in implemented and v not in aliases]
    assert not unreachable, (
        f"{unreachable} would silently render as an ordinary walk — implement a model "
        "in template.html or map it in LOCO_MODEL"
    )


def test_prose_locomotion_resolves_to_a_gait_the_renderer_implements():
    """Every committed Spec carries prose in `locomotion` rather than an enum value, so
    before resolve_gait() all thirteen creatures rendered with the default walk model.

    The two cases below were genuinely miscategorised on the first attempt: a wing
    mentioned for balance must not outrank waddling on legs, and a hedged "possibly
    drifting" must not outrank a stated "immobile".
    """
    import sys

    sys.path.insert(0, str(REPO / "ui"))
    sys.path.insert(0, str(REPO / "skills" / "walk-cycle-anim"))
    from pipeline import resolve_gait

    implemented = _implemented_gaits()
    cases = {
        "walks on four stubby clawed legs, tail fin used for swimming bursts": "walk",
        "waddles on two thin uneven legs, using the single jagged wing-arm for balance": "walk",
        "buzzing flight powered by the single large wing, with dangling legs for landing": "fly",
        "undulates its long ribbon body side to side": "slither",
        "presumed to lie flat and immobile, possibly drifting along flat surfaces": "stumble",
        "drifts and bobs, tethered to nothing": "float",
        "": "stumble",
    }
    for prose, expected in cases.items():
        got = resolve_gait(prose)
        assert got in implemented, f"{got!r} is not a model template.html implements"
        assert got == expected, f"{prose[:40]!r} resolved to {got!r}, wanted {expected!r}"

    # And nothing in the gallery still lands on the old catch-all by accident.
    specs = sorted((REPO / "ui" / "prebuilt").glob("*.spec.json"))
    assert specs, "no bundled specs to check against"
    gaits = {resolve_gait(json.loads(p.read_text()).get("locomotion")) for p in specs}
    assert len(gaits) > 1, f"every creature resolved to the same gait ({gaits}) — dispatch is dead"


def test_bundled_guides_embed_the_same_gait_their_walk_cycle_uses():
    """A guide embeds its walk cycle as a base64 data URI, so it carries a *copy*.
    Rebuilding `<stem>.html` therefore does nothing for `/guide/<stem>` — the guide kept
    serving the animation it was assembled with. That divergence shipped: /anim/bee flew
    while /guide/bee still walked."""
    import base64

    prebuilt = REPO / "ui" / "prebuilt"
    guides = sorted(prebuilt.glob("*.guide.html"))
    assert guides, "no bundled guides to check"

    checked = 0
    for guide in guides:
        stem = guide.name.removesuffix(".guide.html")
        walk = prebuilt / f"{stem}.html"
        if not walk.is_file():
            continue
        embedded = re.search(r'src="data:text/html;base64,([^"]+)"', guide.read_text())
        assert embedded, f"{guide.name}: no embedded walk cycle"
        inner = base64.b64decode(embedded.group(1)).decode("utf-8", "replace")

        def gait(html: str) -> str | None:
            m = re.search(r'"locomotion":\s*"([^"]*)"', html)
            return m.group(1) if m else None

        assert gait(inner) == gait(walk.read_text()), (
            f"{stem}: the guide embeds gait {gait(inner)!r} but its walk cycle uses "
            f"{gait(walk.read_text())!r} — regenerate the .guide.html artifacts"
        )
        checked += 1
    assert checked, "no stem had both a guide and a walk cycle"
