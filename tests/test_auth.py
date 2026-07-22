"""auth.py offline: no real Google OAuth flow anywhere here (that's a third-party
boundary — Authlib's own job to get right, not this repo's), just this module's own
logic: is auth configured, does the domain check pass or fail, and does
require_upload_auth() actually gate on a session.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "ui"
if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))


def _fresh_auth(monkeypatch):
    """auth.py computes _CONFIGURED and registers the OAuth client at import time,
    so a test that changes GOOGLE_CLIENT_ID/etc. needs a genuinely fresh module, not
    whatever's cached in sys.modules from an earlier test or import. monkeypatch.delitem
    (not a bare pop) so the previous sys.modules entry is restored at teardown --
    otherwise the next test to call _load_serve() would pick up THIS test's configured
    auth module regardless of its own env vars, since serve.py's own 'import auth'
    just reads whatever is cached."""
    monkeypatch.delitem(sys.modules, "auth", raising=False)
    import auth

    return auth


def test_unconfigured_without_google_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    auth = _fresh_auth(monkeypatch)
    assert auth._CONFIGURED is False


def test_configured_with_both_credentials(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    auth = _fresh_auth(monkeypatch)
    assert auth._CONFIGURED is True


def test_allowed_domains_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", " fractional.ai, ODE.com ,")
    auth = _fresh_auth(monkeypatch)
    assert auth.allowed_domains() == {"fractional.ai", "ode.com"}


def test_allowed_domains_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ALLOWED_EMAIL_DOMAINS", raising=False)
    auth = _fresh_auth(monkeypatch)
    assert auth.allowed_domains() == set()


class _FakeRequest:
    """Stands in for a Starlette Request — require_upload_auth() only ever touches
    .session, a plain dict, exactly like the real one SessionMiddleware attaches."""

    def __init__(self, session: dict | None = None):
        self.session = session or {}


def test_require_upload_auth_lets_everything_through_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    auth = _fresh_auth(monkeypatch)

    assert auth.require_upload_auth(_FakeRequest()) is None


def test_require_upload_auth_rejects_no_session_when_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    auth = _fresh_auth(monkeypatch)

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        auth.require_upload_auth(_FakeRequest())
    assert exc_info.value.status_code == 401


def test_require_upload_auth_accepts_a_real_session_when_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    auth = _fresh_auth(monkeypatch)

    request = _FakeRequest({"user": {"email": "kid@fractional.ai", "name": "Test Kid"}})
    user = auth.require_upload_auth(request)
    assert user == {"email": "kid@fractional.ai", "name": "Test Kid"}


@pytest.mark.parametrize("present,missing", [("ID", "SECRET"), ("SECRET", "ID")])
def test_half_configured_blocks_uploads_instead_of_opening_them(monkeypatch, present, missing):
    """A typo'd secret in the dashboard must not read as "no auth wanted"."""
    monkeypatch.setenv(f"GOOGLE_CLIENT_{present}", "only-one-of-the-pair")
    monkeypatch.delenv(f"GOOGLE_CLIENT_{missing}", raising=False)
    auth = _fresh_auth(monkeypatch)

    assert auth._CONFIGURED is False
    assert auth._PARTIAL is True

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        auth.require_upload_auth(_FakeRequest())
    assert exc_info.value.status_code == 503


def test_no_credentials_at_all_is_not_partial(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    auth = _fresh_auth(monkeypatch)
    assert auth._PARTIAL is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/guide/shark-dog", "/guide/shark-dog"),
        (None, "/"),
        ("", "/"),
        ("https://evil.example/phish", "/"),
        ("//evil.example/phish", "/"),
        ("javascript:alert(1)", "/"),
    ],
)
def test_safe_next_only_allows_same_site_paths(monkeypatch, raw, expected):
    auth = _fresh_auth(monkeypatch)
    assert auth._safe_next(raw) == expected


class _FakeURL:
    """Starlette's URL.replace(scheme=...) is the only bit _callback_url uses."""

    def __init__(self, url: str):
        self.url = url

    def replace(self, scheme: str) -> _FakeURL:
        return _FakeURL(self.url.replace("http://", f"{scheme}://", 1))

    def __str__(self) -> str:
        return self.url


class _FakeCallbackRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = headers

    def url_for(self, name: str) -> _FakeURL:
        assert name == "auth_callback"
        return _FakeURL("http://stick-figures.example/auth/callback")


def test_callback_url_upgrades_to_https_behind_a_proxy(monkeypatch):
    """Vercel forwards to the function over plain HTTP; Google rejects an http
    redirect_uri, so the forwarded proto has to win."""
    auth = _fresh_auth(monkeypatch)
    request = _FakeCallbackRequest({"x-forwarded-proto": "https"})
    assert auth._callback_url(request) == "https://stick-figures.example/auth/callback"


def test_callback_url_handles_a_comma_joined_proto_chain(monkeypatch):
    auth = _fresh_auth(monkeypatch)
    request = _FakeCallbackRequest({"x-forwarded-proto": "https, http"})
    assert auth._callback_url(request) == "https://stick-figures.example/auth/callback"


def test_callback_url_left_alone_with_no_proxy(monkeypatch):
    auth = _fresh_auth(monkeypatch)
    request = _FakeCallbackRequest({})
    assert auth._callback_url(request) == "http://stick-figures.example/auth/callback"
