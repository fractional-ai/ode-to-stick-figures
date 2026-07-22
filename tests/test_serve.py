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

# A real, tiny, valid 1x1 PNG — needed anywhere a route actually decodes the bytes
# (PIL for upload validation, thumbnailing), not just treats them as an opaque blob.
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


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


def test_upload_route_calls_the_real_build_and_returns_its_result(monkeypatch):
    """The wiring test for /api/upload: no real vision/model call (that's
    upload_build's own offline suite in tests/test_upload_build.py), just proof that
    the route actually calls build_from_upload() in a thread and shapes the response
    from whatever it returns, rather than the route silently doing something else.
    """
    from dataclasses import dataclass

    from fastapi.testclient import TestClient

    serve = _load_serve()

    @dataclass
    class FakeResult:
        id: str
        refused: str | None = None

    calls = []

    def fake_build_from_upload(raw: bytes, suffix: str):
        calls.append((raw, suffix))
        return FakeResult(id="fake0001", refused=None)

    monkeypatch.setattr(serve.upload_build, "build_from_upload", fake_build_from_upload)
    client = TestClient(serve.app)

    r = client.post("/api/upload", files={"file": ("drawing.png", _TINY_PNG, "image/png")})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == "fake0001"
    assert body["refused"] is None
    assert len(calls) == 1
    assert calls[0][1] == ".png"


def test_upload_route_rejects_before_calling_build_from_upload(monkeypatch):
    """The existing fast, cheap gates (bad extension, undecodable bytes) must still
    reject before ever calling build_from_upload() — that call is the expensive one."""
    from fastapi.testclient import TestClient

    serve = _load_serve()

    def fail_if_called(raw: bytes, suffix: str):
        raise AssertionError("build_from_upload() must not run for a rejected upload")

    monkeypatch.setattr(serve.upload_build, "build_from_upload", fail_if_called)
    client = TestClient(serve.app)

    r = client.post("/api/upload", files={"file": ("not-an-image.txt", b"hello", "text/plain")})
    assert r.status_code == 415, r.text


def test_upload_without_an_api_key_503s_instead_of_500ing(monkeypatch):
    """rig_from_image() indexes os.environ["ANTHROPIC_API_KEY"] directly, so with no key
    the upload used to die as an opaque 500 — after the request had been accepted and
    the expensive path entered. Say so up front instead."""
    from fastapi.testclient import TestClient

    serve = _load_serve()
    monkeypatch.setattr(serve, "HAVE_KEY", False)

    def fail_if_called(raw: bytes, suffix: str):
        raise AssertionError("build_from_upload() must not run without an API key")

    monkeypatch.setattr(serve.upload_build, "build_from_upload", fail_if_called)
    client = TestClient(serve.app)

    r = client.post("/api/upload", files={"file": ("drawing.png", _TINY_PNG, "image/png")})
    assert r.status_code == 503, r.text
    assert "ANTHROPIC_API_KEY" in r.json()["error"]


def _seed_upload(serve, storage, stem: str, *, refused: str | None = None):
    """Write the artifact set upload_build.py's _sync_dir() would have produced for
    a real upload, directly into a Storage instance — then point serve.UPLOAD_STORAGE
    at it. Lets these tests drive the real routes against an "uploaded" creature
    without a real vision/model call anywhere."""
    import json

    serve.UPLOAD_STORAGE = storage
    if refused:
        storage.write_bytes(
            f"{stem}.rig.json", json.dumps({"refuse": True, "refuse_reason": refused}).encode()
        )
        return
    storage.write_bytes(f"{stem}.png", _TINY_PNG)
    storage.write_bytes(f"{stem}.rig.json", json.dumps({"name": "Test Upload"}).encode())
    storage.write_bytes(f"{stem}.spec.json", json.dumps({"name": "Test Upload"}).encode())
    storage.write_bytes(f"{stem}.html", b"<html>fake walk cycle</html>")
    storage.write_bytes(f"{stem}.guide.html", b"<html><body>fake guide</body></html>")


def test_uploaded_creature_is_fully_servable(monkeypatch, tmp_path):
    """The whole point of this migration: an uploaded creature must be servable the
    same way a bundled one is — /anim, /guide, /thumb, and present in the listing."""
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    store = LocalStorage(tmp_path / "uploads")
    _seed_upload(serve, store, "up-abc123")
    client = TestClient(serve.app)

    anim_r = client.get("/anim/up-abc123")
    assert anim_r.status_code == 200, anim_r.text
    assert "fake walk cycle" in anim_r.text

    # /guide serves a wrapper, not the model-written HTML — see _sandboxed_guide_page.
    guide_r = client.get("/guide/up-abc123")
    assert guide_r.status_code == 200, guide_r.text
    assert "fake guide" not in guide_r.text
    assert 'sandbox="allow-scripts allow-popups"' in guide_r.text
    assert "/guide/up-abc123/raw" in guide_r.text

    raw_r = client.get("/guide/up-abc123/raw")
    assert raw_r.status_code == 200, raw_r.text
    assert "fake guide" in raw_r.text

    thumb_r = client.get("/thumb/up-abc123")
    assert thumb_r.status_code == 200, thumb_r.text
    assert thumb_r.headers["content-type"] == "image/png"

    creatures = client.get("/api/creatures").json()
    card = next((c for c in creatures if c["stem"] == "up-abc123"), None)
    assert card is not None, "uploaded creature is missing from the listing entirely"
    assert card["animated"] is True
    assert card["uploaded"] is True
    assert card["name"] == "Test Upload"


def test_uploaded_refusal_holds_on_the_routes(monkeypatch, tmp_path):
    """A refused upload must behave exactly like a refused bundled creature (e.g.
    snowmen-scene): 422 on both /anim and /guide, never reaching any build attempt."""
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    store = LocalStorage(tmp_path / "uploads")
    _seed_upload(serve, store, "up-refused1", refused="no animal in this drawing")
    client = TestClient(serve.app)

    for route in ("/anim/up-refused1", "/guide/up-refused1"):
        r = client.get(route)
        assert r.status_code == 422, f"{route}: {r.text}"
        assert "no animal in this drawing" in r.text

    creatures = client.get("/api/creatures").json()
    card = next(c for c in creatures if c["stem"] == "up-refused1")
    assert card["refused"] == "no animal in this drawing"
    assert card["animated"] is False


def test_uploaded_creature_still_building_degrades_instead_of_404ing(monkeypatch, tmp_path):
    """A rig exists (the vision pass finished) but no guide/anim yet -- either the
    build is still running or it crashed partway. That's a different, more honest
    answer than "no rig for this drawing yet", which implies nothing happened at all.
    """
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("up-midbuild.rig.json", b'{"name": "Mid Build"}')
    serve.UPLOAD_STORAGE = store
    client = TestClient(serve.app)

    anim_r = client.get("/anim/up-midbuild")
    assert anim_r.status_code == 503, anim_r.text

    guide_r = client.get("/guide/up-midbuild")
    assert guide_r.status_code == 503, guide_r.text


def test_uploaded_guide_script_cannot_reach_the_gallerys_origin(monkeypatch, tmp_path):
    """The XSS containment, stated as the property that matters: an uploader's script
    never executes with the gallery's origin.

    Uses a guide whose body is an actual payload, and checks both doors — the page a
    visitor loads, and the raw URL an attacker would send them to directly.
    """
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    payload = b"<html><body><script>fetch('/api/steal?c='+document.cookie)</script></body></html>"
    store = LocalStorage(tmp_path / "uploads")
    _seed_upload(serve, store, "up-evil")
    store.write_bytes("up-evil.guide.html", payload)
    client = TestClient(serve.app)

    # Door 1: the wrapper never inlines the payload, so nothing runs first-party.
    wrapper = client.get("/guide/up-evil")
    assert wrapper.status_code == 200
    assert "document.cookie" not in wrapper.text
    assert 'sandbox="allow-scripts allow-popups"' in wrapper.text

    # Door 2: opened directly, the CSP header re-applies the same sandbox, so the
    # script still runs in an opaque origin rather than ours.
    raw = client.get("/guide/up-evil/raw")
    assert raw.status_code == 200
    assert "document.cookie" in raw.text, "the guide itself is served, just contained"
    csp = raw.headers["content-security-policy"]
    assert csp == "sandbox allow-scripts allow-popups"
    assert "allow-same-origin" not in csp, "allow-same-origin would undo the whole point"


def test_bundled_guide_has_no_raw_route(monkeypatch, tmp_path):
    """Bundled guides are repo-authored and served directly; /raw is for uploads only."""
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    serve.UPLOAD_STORAGE = LocalStorage(tmp_path / "uploads")
    client = TestClient(serve.app)

    assert client.get("/guide/bee/raw").status_code == 404


def test_rig_only_upload_is_not_advertised_as_animated(monkeypatch, tmp_path):
    """A build that died after the rig, or a partial Blob sync. /anim and /guide both
    503 in that state, so a card claiming "animated" links to two broken pages."""
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    store = LocalStorage(tmp_path / "uploads")
    store.write_bytes("up-halfbuilt.rig.json", b'{"name": "Half Built"}')
    store.write_bytes("up-halfbuilt.png", _TINY_PNG)
    serve.UPLOAD_STORAGE = store
    client = TestClient(serve.app)

    card = next(c for c in client.get("/api/creatures").json() if c["stem"] == "up-halfbuilt")
    assert card["animated"] is False
    assert client.get("/anim/up-halfbuilt").status_code == 503
    assert client.get("/guide/up-halfbuilt").status_code == 503


def test_unknown_upload_stem_still_404s(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    serve = _load_serve()
    from storage import LocalStorage

    serve.UPLOAD_STORAGE = LocalStorage(tmp_path / "uploads")
    client = TestClient(serve.app)

    assert client.get("/anim/nothing-here-at-all").status_code == 404
    assert client.get("/guide/nothing-here-at-all").status_code == 404
    assert client.get("/thumb/nothing-here-at-all").status_code == 404


def test_upload_route_requires_auth_when_configured(monkeypatch):
    """The actual wiring test: Depends(auth.require_upload_auth) on POST /api/upload
    must really block an unauthenticated request once GOOGLE_CLIENT_ID/SECRET are
    set, not just in auth.py's own isolated unit tests. serve.py's `import auth` is
    a normal import, cached in sys.modules -- monkeypatch.delitem it first (not a bare
    pop) so the fresh serve.py exec below re-executes auth.py against these env vars,
    and the real cache entry is restored afterward rather than leaking a "configured"
    auth module into whichever test happens to run next.
    """
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.delitem(sys.modules, "auth", raising=False)

    serve = _load_serve()
    client = TestClient(serve.app)

    def fail_if_called(raw: bytes, suffix: str):
        raise AssertionError("build_from_upload() must not run for an unauthenticated upload")

    monkeypatch.setattr(serve.upload_build, "build_from_upload", fail_if_called)

    r = client.post("/api/upload", files={"file": ("drawing.png", _TINY_PNG, "image/png")})
    assert r.status_code == 401, r.text


def test_login_redirects_to_google_when_configured(monkeypatch):
    """/login doesn't exist at all when auth is unconfigured (see
    test_upload_route_calls_the_real_build_and_returns_its_result's sibling checks in
    the unconfigured suite) -- once configured, it must exist and start a real OAuth
    redirect. Doesn't touch Google for real: authorize_redirect() needs the
    discovery document Google actually serves, which is a live network call this
    offline suite has no business making. Mocked at exactly that boundary."""
    from unittest.mock import AsyncMock

    from fastapi.responses import RedirectResponse
    from fastapi.testclient import TestClient

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.delitem(sys.modules, "auth", raising=False)

    serve = _load_serve()
    monkeypatch.setattr(
        serve.auth.oauth.google,
        "authorize_redirect",
        AsyncMock(return_value=RedirectResponse("https://accounts.google.com/o/oauth2/fake")),
    )
    client = TestClient(serve.app, follow_redirects=False)

    r = client.get("/login")
    assert r.status_code in (302, 307), r.text
    assert "accounts.google.com" in r.headers["location"]
