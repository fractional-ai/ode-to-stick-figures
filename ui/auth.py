"""Google sign-in, gating uploads to a real Workspace domain.

Nothing else in the gallery needs a login. The whole point of this migration was to
keep browsing public while gating the one action that costs real money and writes
real content into the gallery — see require_upload_auth(), the only place this
module's gate actually applies. Every other route is untouched.

Configuration is via env vars (GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SESSION_SECRET,
ALLOWED_EMAIL_DOMAINS), not hardcoded. Two reasons: a Google OAuth client ID isn't
something to commit, and the allowed domain is a comma-separated list rather than a
constant because the org is mid-rename from fractional.ai to ode.com and may need to
add the new domain without a code change.

If GOOGLE_CLIENT_ID/SECRET aren't set, auth is off entirely: install() registers no
routes, and require_upload_auth() lets every upload through. This is deliberate, not
an oversight — setting up a real Google OAuth client (a registered redirect URI,
etc.) is a real hurdle nobody should have to clear just to run the gallery locally.
The requirement in the plan this implements was about hosting a real deployment, not
about every dev machine.
"""

from __future__ import annotations

import html
import os

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pages import error_page
from starlette.middleware.sessions import SessionMiddleware

oauth = OAuth()


def _creds() -> tuple[str | None, str | None]:
    """Read every time, never cached at import.

    This used to be module-level constants, which made the gate depend on import order:
    serve.py's `import auth` runs before its load_env(), so credentials supplied through
    a .env file weren't in os.environ yet and auth read as "off" — silently ungating
    uploads on exactly the .env-based setups most likely to be someone's first real
    deploy. Reading lazily means no caller can get that wrong.
    """
    return os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")


def is_configured() -> bool:
    client_id, client_secret = _creds()
    return bool(client_id and client_secret)


def is_partial() -> bool:
    """Exactly one of the two set. Not the same thing as "auth is off": all-empty is a
    dev machine deliberately running without a login, but half-empty is a deployment
    someone meant to gate and typo'd. Treating that as "off" would silently open uploads
    — so it blocks them instead (see require_upload_auth), leaving the gallery up."""
    client_id, client_secret = _creds()
    return bool(client_id or client_secret) and not (client_id and client_secret)


def _callback_url(request: Request) -> str:
    """The redirect_uri handed to Google, which must match a registered one exactly.

    Vercel terminates TLS at the edge and forwards the request to the function over
    plain HTTP, so request.url_for() builds an `http://` URI there — which Google
    rejects for anything but localhost. Trust x-forwarded-proto when it's present;
    with no proxy in front (a dev machine) there's no header and nothing changes.
    """
    url = request.url_for("auth_callback")
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return str(url.replace(scheme=proto) if proto else url)


def _safe_next(raw: str | None) -> str:
    """Only same-site relative paths. `?next=https://evil.example` would otherwise make
    this an open redirect that borrows the gallery's domain for a phishing hop."""
    if raw and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return "/"


def allowed_domains() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAIL_DOMAINS", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def install(app: FastAPI) -> None:
    """Wire the session middleware and /login, /auth/callback onto `app`. No-op if
    GOOGLE_CLIENT_ID/SECRET aren't set — see the module docstring for why."""
    if not is_configured():
        return

    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        raise SystemExit("SESSION_SECRET must be set when GOOGLE_CLIENT_ID is configured.")
    app.add_middleware(SessionMiddleware, secret_key=secret)

    client_id, client_secret = _creds()
    oauth.register(
        name="google",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    @app.get("/login")
    async def login(request: Request):
        # Google doesn't forward our query params to the callback, so where the user was
        # headed has to ride in the session or it's lost across the roundtrip.
        request.session["next"] = _safe_next(request.query_params.get("next"))
        return await oauth.google.authorize_redirect(request, _callback_url(request))

    @app.get("/auth/callback")
    async def auth_callback(request: Request):
        token = await oauth.google.authorize_access_token(request)
        # token["userinfo"] is the signed ID token's claims, verified by authlib
        # against Google's JWKS — not user-supplied data, safe to gate on.
        userinfo = token.get("userinfo") or {}
        domain = str(userinfo.get("hd") or "").lower()
        if domain not in allowed_domains():
            who = html.escape(str(userinfo.get("email") or "That account"))
            return error_page(
                status=403,
                heading="Not an allowed domain",
                body=f"<p>{who} isn't on an allowed domain for uploading. "
                "Browsing the gallery never needs a sign-in.</p>",
            )
        request.session["user"] = {"email": userinfo.get("email"), "name": userinfo.get("name")}
        # Re-checked on the way out, not just on the way in: the session is signed, but
        # _safe_next is cheap and this keeps the guarantee at the redirect itself.
        return RedirectResponse(_safe_next(request.session.pop("next", None)))

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/")


def require_upload_auth(request: Request) -> dict | None:
    """FastAPI dependency gating uploads to a signed-in, domain-allowed user. Applied
    via Depends() ONLY on POST /api/upload.

    request.session raises AssertionError, not a clean 401, if SessionMiddleware was
    never installed (auth not configured) — so check is_configured() first rather than
    let that surface as an opaque 500 for every upload on an unconfigured deployment.
    """
    if is_partial():
        raise HTTPException(
            status_code=503,
            detail="Upload auth is misconfigured on this deployment; uploads are disabled.",
        )
    if not is_configured():
        return None
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to upload.")
    return user
