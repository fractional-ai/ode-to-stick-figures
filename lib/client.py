"""Shared Anthropic client for the managed-agents preview.

Defined once so the beta header is present on every beta.* call. The original
workshop repo set this header on only some scripts, which fails silently
against the preview endpoints.
"""

import os

from anthropic import Anthropic

MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


def managed_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")
    return Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": MANAGED_AGENTS_BETA},
    )
