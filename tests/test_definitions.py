"""Contracts around the agent definitions — not their wording.

This file used to assert that particular words appeared in particular prompts
("literal", "shark", each lane's name in the coordinator prompt). Those are deleted: a
substring check on a prompt only restates what the file already says, it passes whether
or not the prompt works, and it fails on a reword that changed nothing. Whether a
prompt actually produces a good Creature Spec is an eval — see evals/ — and that is
where any assertion about prompt quality belongs.

What is left is the stuff a prompt or schema edit can genuinely break somewhere else.
"""

import json
import re
from pathlib import Path

from agents import definitions as d

REPO = Path(__file__).resolve().parents[1]


def test_specialist_keys_match_what_the_pipeline_fans_out_to():
    """pipeline.py selects text lanes by exact key (`a["key"] in ("biologist",
    "habitat", "society")`). Rename one here and that filter silently drops a lane — the
    guide loses a whole section and nothing errors. Replaces a test that only asserted
    the keys this file visibly defines."""
    keys = {s["key"] for s in d.SPECIALISTS}
    assert {"biologist", "habitat", "society", "modeler"} <= keys

    fan_out = (REPO / "ui" / "pipeline.py").read_text()
    selected = re.search(r'a\["key"\] in \(([^)]*)\)', fan_out).group(1)
    for key in re.findall(r'"(\w+)"', selected):
        assert key in keys, f"pipeline.py fans out to {key!r}, which no specialist defines"


# --- the gait dispatch -------------------------------------------------------
# These check contracts that span two files and can silently drift, which is what
# happened here: the renderer implemented a gait the schema couldn't ask for, the
# schema offered five the renderer had never heard of, and every committed Spec
# carried prose that matched none of them.


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
