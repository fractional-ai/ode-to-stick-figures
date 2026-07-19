"""Every gallery route answers, for every drawing we ship.

This file exists because of a bug we shipped three times. Editing serve.py or
index.html and checking that the gallery returns 200 does not prove anything: the
gallery is a static page listing creatures, and it renders fine while every button
on it is broken. Twice a refactor deleted a live function or handler as collateral
(`animation()` in one case, the dialog's Close handler in another), the gallery kept
returning 200, and the break shipped.

So: walk the actual routes, for every drawing, and assert on status. These are cache
hits against checked-in artifacts, so the suite stays offline and fast — no API key,
no model calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.conftest import load_module_from_path

UI = Path(__file__).resolve().parents[1] / "ui"
SKILL = Path(__file__).resolve().parents[1] / "skills" / "walk-cycle-anim"


def _load_serve():
    for p in (UI, SKILL):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    return load_module_from_path("serve", UI / "serve.py")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    return TestClient(_load_serve().app)


@pytest.fixture(scope="module")
def creatures(client):
    r = client.get("/api/creatures")
    assert r.status_code == 200
    items = r.json()
    assert items, "no drawings found at all"
    return items


def test_gallery_serves(client):
    assert client.get("/").status_code == 200


def test_every_animated_creature_has_a_working_walk(creatures, client):
    """The one that matters. A 500 here is the gallery's ▶ walk button being dead."""
    animated = [c for c in creatures if c["animated"]]
    assert animated, "nothing is animated — the gallery has nothing to show"
    codes = {c["stem"]: client.get(f"/anim/{c['stem']}").status_code for c in animated}
    broken = {stem: code for stem, code in codes.items() if code != 200}
    assert not broken, f"/anim/ is broken for: {broken}"


def test_every_creature_has_a_thumbnail(creatures, client):
    codes = {c["stem"]: client.get(f"/thumb/{c['stem']}").status_code for c in creatures}
    broken = {stem: code for stem, code in codes.items() if code != 200}
    assert not broken, f"/thumb/ is broken for: {broken}"


def test_animation_carries_the_spec_name_not_the_rigs(creatures, client):
    """The animation, the card and the guide must name the same creature.

    The gallery rebuilds an animation whenever the renderer template is newer than the
    build. That rebuild has to go through the swarm's Spec overrides; when it called
    bare build() instead, it reverted to the rig's own name, palette and environment,
    so millipede's guide said Fringed Bristleback Eel while its animation said
    Thousand-Foot Noodle.
    """
    import json

    serve = _load_serve()
    checked = 0
    for c in creatures:
        if not c["animated"]:
            continue
        spec_file = serve.PREBUILT / f"{c['stem']}.spec.json"
        if not spec_file.is_file():
            continue
        from pipeline import flat

        name = flat(json.loads(spec_file.read_text()).get("name"))
        if not name:
            continue
        html = client.get(f"/anim/{c['stem']}").text
        assert name in html, f"{c['stem']}: animation doesn't carry the Spec name {name!r}"
        checked += 1
    assert checked, "no creature had a cached Spec to check against"


def test_refused_drawings_do_not_claim_to_animate(creatures, client):
    """A refusal is a real answer; it must not be advertised as animated."""
    for c in creatures:
        if c["refused"]:
            assert not c["animated"], f"{c['stem']} is refused but marked animated"


def test_refused_drawings_are_refused_by_the_routes_too(creatures, client):
    """A refusal has to hold on the route, not just on the card.

    This assertion is the one that was missing. The test above only checks the listing
    agrees with itself, so hiding the buttons looked like enough. It wasn't: /anim/ and
    /guide/ never consulted refusal(), and a direct URL walked straight past it. Hitting
    /guide/snowmen-scene ran the whole swarm on a painting of two snowmen and invented
    "Segmented Bucket-Hat Wader (Segmentus caputbalneus)" with locomotion "float", then
    wrote it into ui/prebuilt/ where it got committed. Real model calls spent to
    manufacture exactly the plausible garbage the refusal exists to prevent.
    """
    refused = [c["stem"] for c in creatures if c["refused"]]
    assert refused, "no refused drawing in the gallery to test the bail path with"
    for stem in refused:
        for route in (f"/anim/{stem}", f"/guide/{stem}"):
            r = client.get(route)
            assert r.status_code == 422, (
                f"{route} returned {r.status_code}, not a refusal — it is doing the work"
            )


def test_unknown_stem_404s(client):
    assert client.get("/anim/no-such-creature").status_code == 404
    assert client.get("/thumb/no-such-creature").status_code == 404


def test_on_vercel_a_prebuild_miss_degrades_instead_of_writing(monkeypatch, tmp_path):
    """On Vercel, a cache miss for a bundled creature must never attempt run_swarm().

    The filesystem is read-only outside /tmp there, and animation()'s rebuild plus
    get_guide()'s run_swarm() both write into PREBUILT on a miss. Simulate the
    real failure mode without actually pointing at a read-only filesystem: load serve
    with VERCEL=1 so ON_VERCEL is computed True, then redirect its PREBUILT constant to
    an empty directory so every real, rigged creature looks like a missed prewarm. If
    this test ever starts hitting run_swarm() instead of degrading, it will try to call
    the live API and fail loudly (no ANTHROPIC_API_KEY in CI) rather than silently pass.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("VERCEL", "1")
    serve = _load_serve()
    monkeypatch.setattr(serve, "PREBUILT", tmp_path)
    client = TestClient(serve.app)

    r = client.get("/api/creatures")
    animated = [c for c in r.json() if c["animated"]]
    assert animated, "need at least one real rigged creature to test against"
    stem = animated[0]["stem"]

    anim_r = client.get(f"/anim/{stem}")
    assert anim_r.status_code == 503, anim_r.text
    assert "prewarm.py" in anim_r.text

    guide_r = client.get(f"/guide/{stem}")
    assert guide_r.status_code == 503, guide_r.text
    assert "prewarm.py" in guide_r.text
