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
