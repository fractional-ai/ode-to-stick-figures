"""Shared test fixtures and helpers.

load_module_from_path exists because three test files each hand-rolled the same
importlib dance to load a module by file path rather than by package name (the
modules live in skills/*/ directories with hyphens, which can't be import
statements). One copy, with the None-checks mypy wants and that a real existing
file can never actually trigger.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_module_from_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None, f"no spec for {path}"
    assert spec.loader is not None, f"no loader for {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pytest_configure() -> None:
    """Pin Logfire to local-only for the whole suite.

    Without this the first span in a test auto-configures the SDK and warns about it,
    and a developer who happens to have LOGFIRE_TOKEN exported — it lives in a .env one
    directory above this repo — would ship test traces to the real project. The suite is
    offline by contract; that has to include telemetry.
    """
    import os

    import logfire

    # Both halves matter. The env var stops the app's own telemetry.install() from
    # reconfiguring over this pin (logfire.configure is last-call-wins), and the
    # configure call here means a span in a test doesn't auto-configure and warn.
    os.environ["ODE_TELEMETRY"] = "off"
    logfire.configure(send_to_logfire=False, console=False)
