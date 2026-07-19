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

import os

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

_CONFIGURED = bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))

oauth = OAuth()
if _CONFIGURED:
    oauth.register(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def allowed_domains() -> set[str]:
    raw = os.environ.get("ALLOWED_EMAIL_DOMAINS", "")
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def install(app: FastAPI) -> None:
    """Wire the session middleware and /login, /auth/callback onto `app`. No-op if
    GOOGLE_CLIENT_ID/SECRET aren't set — see the module docstring for why."""
    if not _CONFIGURED:
        return

    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        raise SystemExit("SESSION_SECRET must be set when GOOGLE_CLIENT_ID is configured.")
    app.add_middleware(SessionMiddleware, secret_key=secret)

    @app.get("/login")
    async def login(request: Request):
        redirect_uri = request.url_for("auth_callback")
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @app.get("/auth/callback")
    async def auth_callback(request: Request):
        token = await oauth.google.authorize_access_token(request)
        # token["userinfo"] is the signed ID token's claims, verified by authlib
        # against Google's JWKS — not user-supplied data, safe to gate on.
        userinfo = token.get("userinfo") or {}
        domain = str(userinfo.get("hd") or "").lower()
        if domain not in allowed_domains():
            return HTMLResponse(
                f"<p>{userinfo.get('email', 'That account')} isn't on an allowed "
                "domain for uploading.</p>",
                status_code=403,
            )
        request.session["user"] = {"email": userinfo.get("email"), "name": userinfo.get("name")}
        next_url = request.query_params.get("next") or "/"
        return RedirectResponse(next_url)

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/")


def require_upload_auth(request: Request) -> dict | None:
    """FastAPI dependency gating uploads to a signed-in, domain-allowed user. Applied
    via Depends() ONLY on POST /api/upload.

    request.session raises AssertionError, not a clean 401, if SessionMiddleware was
    never installed (auth not configured) — so check _CONFIGURED first rather than
    let that surface as an opaque 500 for every upload on an unconfigured deployment.
    """
    if not _CONFIGURED:
        return None
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Sign in to upload.")
    return user
