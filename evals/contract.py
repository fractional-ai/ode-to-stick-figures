"""
Frozen contracts for the Creature Spec eval harness.

This file is the seam between the runner (run_evals.py) and the two pluggable
halves (checks.py, cases.py). Freeze it first; everything else keys off it.

The unit under test is the Field Interpreter's output: a single creature-spec
JSON object. Every downstream agent (Biologist, Habitat, Society, 3D Modeler)
depends on this shape, so these evals guard the most important seam in the swarm.

AUTHORITATIVE SOURCE OF TRUTH: the machine-readable JSON Schema at
contracts/creature-spec.schema.json. checks.py validates every
spec against it and reads enum values (core_shape, locomotion) straight out of
it, so the checks can never drift from the frozen contract. The constants below
mirror that schema for cheap, dependency-free field checks — if the schema
changes, they follow it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Creature Spec schema (mirrors specs/2026-07-17-creature-swarm-design.md)     #
# --------------------------------------------------------------------------- #
# A valid creature-spec.json looks like:
#
# {
#   "name": "Speckled Waddler (Globus maculatus)",
#   "body_plan": {
#     "core_shape": "sphere|ovoid|slab|...",
#     "symmetry": "bilateral|radial",
#     "size_est_m": 0.4
#   },
#   "parts": [
#     {"type": "leg", "count": 6, "shape": "...", "placement": "..."}
#   ],
#   "palette": ["#aabbcc", "..."],
#   "distinctive_features": ["forked tail", "bioluminescent spots"],
#   "locomotion": "waddle|hop|slither|...",
#   "vibe": "one-line personality"
# }

# Top-level keys every spec MUST have.
REQUIRED_TOP_LEVEL_KEYS = (
    "name",
    "body_plan",
    "parts",
    "palette",
    "distinctive_features",
    "locomotion",
    "vibe",
)

# Keys required inside body_plan.
REQUIRED_BODY_PLAN_KEYS = ("core_shape", "symmetry", "size_est_m")

# Keys required inside each entry of parts[].
REQUIRED_PART_KEYS = ("type", "count", "shape", "placement")

# Allowed values for body_plan.symmetry.
VALID_SYMMETRIES = ("bilateral", "radial")


# --------------------------------------------------------------------------- #
# Check contract                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class CheckResult:
    """Result of a single check against one creature spec."""

    name: str  # short check id, e.g. "valid-json" or "palette-is-hex"
    passed: bool
    detail: str = ""  # human-readable reason, shown on failure

    @property
    def symbol(self) -> str:
        return "PASS" if self.passed else "FAIL"


# A deterministic check is any callable with this signature. Case is defined below;
# a PEP 695 type alias's value is lazily evaluated, so the forward reference is fine.
#
# It must NOT raise on a bad spec — catch and return CheckResult(passed=False). No
# type can express that; it's a runtime contract, stated here instead.
type Check = Callable[[dict, Case], CheckResult]

# checks.py must expose:
#     DETERMINISTIC_CHECKS: list[Check]   # the deterministic checks
#     llm_judge_check(spec: dict, case: Case) -> CheckResult   # the one LLM judge


# --------------------------------------------------------------------------- #
# Case contract                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class Case:
    """One eval case: an input drawing + how to evaluate its spec."""

    id: str  # "bee", "shark-dog", ...
    drawing_path: str  # examples/drawings/bee.webp
    fixture_path: str  # evals/fixtures/bee.json
    expected_features: list[str] = field(default_factory=list)  # hints for the LLM judge
    notes: str = ""  # free-text, e.g. what the drawing shows


# cases.py must expose:
#     CASES: list[Case]
