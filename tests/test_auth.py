"""auth.py offline: no real Google OAuth flow anywhere here (that's a third-party
boundary — Authlib's own job to get right, not this repo's), just this module's own
logic: is auth configured, does the domain check pass or fail, and does
require_upload_auth() actually gate on a session.
"""

from __future__ import annotations

import sys
from pathlib import Path

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
