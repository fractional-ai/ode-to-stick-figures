"""One styled page for every non-happy path.

Refusals, 404s, prewarm/build notices, and the auth domain rejection each used to be
a bare ``<p>`` on a blank white page (14px Times, no way back), which reads as a crash
rather than an answer — while the gallery card for the same refusal gets the full
treatment. They all render through error.html now: the gallery's paper-and-ink look,
the wordmark, and a link back.

Lives in its own module so both serve.py and auth.py can share it without serve.py's
import of auth.py becoming a cycle. `heading` and `body` are trusted HTML — callers
escape any dynamic text (a refusal reason, an email) before passing it in.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse

_TEMPLATE = (Path(__file__).resolve().parent / "error.html").read_text()


def error_page(*, status: int, heading: str, body: str, code: str | None = None) -> HTMLResponse:
    """A full, styled page carrying `status`. `heading` is the page title/heading and
    `body` is the message HTML (both trusted — callers escape dynamic text). `code` is
    the small monospace label above the heading; defaults to "Error {status}"."""
    slots = {"code": code or f"Error {status}", "heading": heading, "body": body}
    html = _TEMPLATE
    for key, value in slots.items():
        html = html.replace("{{" + key + "}}", value)
    return HTMLResponse(html, status_code=status)
