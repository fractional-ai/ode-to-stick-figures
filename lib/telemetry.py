"""Logfire setup: one call, and nothing at all without a token.

Why this exists as its own module rather than four lines in serve.py: the swarm runs
from more than one entry point (the gallery, ui/prewarm.py, the eval harness), and
`logfire.configure()` is a once-per-process call. A shared, idempotent installer means
any entry point can ask for instrumentation without the second caller silently
reconfiguring the SDK out from under the first.

`send_to_logfire="if-token-present"` is the load-bearing argument. The test suite is
offline by contract (see tests/test_serve.py's docstring) and CI has no LOGFIRE_TOKEN,
so instrumentation has to degrade to spans that are created and discarded rather than
to an error or a network call. Spans still nest correctly with no token, which is what
lets the same code path be traced in production and silent in a test.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_INSTALLED = False

# Set by tests/conftest.py. `logfire.configure()` is last-call-wins, so without this the
# app's own install() would reconfigure straight over the suite's send_to_logfire=False
# pin — and a developer with LOGFIRE_TOKEN exported (it lives in a .env one directory
# above this repo) would ship test traces to the real project. Found exactly that way.
_OFF_SWITCH = "ODE_TELEMETRY"


def install(app: FastAPI | None = None) -> None:
    """Configure Logfire once, and instrument what this app actually uses.

    Safe to call from any entry point and safe to call twice. Pass the FastAPI app to
    get request spans; omit it for the CLI paths (prewarm, evals) that have no server.
    """
    global _INSTALLED
    if _INSTALLED or os.environ.get(_OFF_SWITCH) == "off":
        return
    _INSTALLED = True

    # Cap attribute size BEFORE configure(), because the tracer provider reads OTel's
    # limits when it's built.
    #
    # This is not a nice-to-have. instrument_anthropic() records the request body, and
    # every vision call in this pipeline carries a base64 PNG of a child's drawing — a
    # keyed 12MP photo is megabytes. Measured with a 16KB test image: the full base64
    # landed in `request_data` on two separate spans, 34KB of span payload for 16KB of
    # image. At real sizes that is multi-megabyte spans on every upload, which costs
    # quota, risks the span being dropped outright, and ships children's drawings to a
    # third party for no diagnostic benefit. 4096 chars keeps the useful head of a
    # request (model, message shape) and throws the pixels away.
    os.environ.setdefault("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", "4096")

    import logfire

    logfire.configure(
        service_name="ode-to-stick-figures",
        # Separates production traces from preview ones, which matters because a
        # preview deploy exercises the same expensive upload path against the same
        # Blob store. VERCEL_ENV is populated once system env vars are enabled.
        environment=os.environ.get("VERCEL_ENV", "local"),
        send_to_logfire="if-token-present",
        # Vercel already writes one log line per request, and console spans would
        # interleave a second, much noisier copy into the same stream.
        console=False,
    )

    # httpx covers both outbound directions worth seeing: Anthropic's transport and
    # ui/storage.py's hand-rolled Vercel Blob calls, which have no SDK of their own and
    # were where four separate bugs hid.
    logfire.instrument_httpx()
    # Token usage and model per call, which is the number that turns "the build was
    # slow" into "which lane was slow and what did it cost".
    logfire.instrument_anthropic()
    if app is not None:
        logfire.instrument_fastapi(app)
