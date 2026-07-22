"""Vercel entrypoint shim.

Vercel's Python/FastAPI runtime looks for an `app` variable in specific default
filenames/locations (app.py, index.py, main.py, including under api/) — ui/serve.py
doesn't match that convention by name or location, so this file exists purely to be
found there and re-export the real app. No logic of its own.

Uses the same sys.path-insertion pattern ui/serve.py itself already uses for its own
sibling imports (from build_walk_cycle import ..., from pipeline import ...), rather
than `from ui.serve import app` — ui/ has no __init__.py, so that would depend on
whatever namespace-package resolution Vercel's bundler happens to do, instead of the
explicit, already-proven mechanism the rest of this codebase relies on.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ui"))

from serve import app  # noqa: E402

__all__ = ["app"]
