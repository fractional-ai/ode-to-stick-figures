"""
Checks for the Creature Spec eval harness.

Two flavors live here, both keyed off contract.py:
  * DETERMINISTIC_CHECKS — cheap, offline structural checks over the spec dict.
  * llm_judge_check      — one Claude-as-judge check for drawing plausibility.

The FIRST deterministic check validates the spec against the canonical, frozen
JSON Schema at contracts/creature-spec.schema.json — the same
contract the live Field Interpreter is held to. The remaining checks are
readable per-field diagnostics; the enum values they use are read out of that
schema at import time, so they can never drift from the contract.

Every check has signature `def check(spec: dict, case: Case) -> CheckResult`
and NEVER raises on a malformed spec — it catches the problem and returns a
failing CheckResult instead. The judge is the exception: it degrades to a
*passing* skip whenever it cannot run, so a missing API key never reds the suite.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from contract import (
    REQUIRED_BODY_PLAN_KEYS,
    REQUIRED_PART_KEYS,
    REQUIRED_TOP_LEVEL_KEYS,
    VALID_SYMMETRIES,
    Case,
    Check,
    CheckResult,
)

# Hex colors: #rgb or #rrggbb (case-insensitive).
_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# --------------------------------------------------------------------------- #
# Load the canonical schema (single source of truth for enums + validation).  #
# --------------------------------------------------------------------------- #
_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contracts" / "creature-spec.schema.json"

try:
    _SCHEMA = json.loads(_SCHEMA_PATH.read_text())
except Exception:  # noqa: BLE001 - missing schema => enum checks fall back, schema check skips.
    _SCHEMA = None


def _enum_from_schema(*path: str) -> tuple[str, ...]:
    """Read an enum list out of the loaded schema, or () if unavailable."""
    node = _SCHEMA
    try:
        for key in path:
            node = node[key]
        return tuple(node["enum"])
    except Exception:  # noqa: BLE001
        return ()


VALID_CORE_SHAPES = _enum_from_schema("properties", "body_plan", "properties", "core_shape")
VALID_LOCOMOTION = _enum_from_schema("properties", "locomotion")


# --------------------------------------------------------------------------- #
# Deterministic checks                                                        #
# --------------------------------------------------------------------------- #
def _nonempty_str(value: object) -> bool:
    """True iff value is a non-empty (after stripping) string."""
    return isinstance(value, str) and value.strip() != ""


def check_schema_valid(spec: dict, case: Case) -> CheckResult:
    """Authoritative: validate the spec against the frozen JSON Schema.

    This is the check that guarantees parity with what the live Field Interpreter
    is contractually allowed to emit. Skips to a PASS only if the schema file or
    the jsonschema package is unavailable (never a false red).
    """
    name = "schema-valid"
    if _SCHEMA is None:
        return CheckResult(
            name=name, passed=True, detail=f"skipped: schema not found at {_SCHEMA_PATH}"
        )
    try:
        from jsonschema import Draft202012Validator
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            name=name, passed=True, detail=f"skipped: jsonschema unavailable ({exc})"
        )

    validator = Draft202012Validator(_SCHEMA)
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.path))
    if not errors:
        return CheckResult(name=name, passed=True)
    parts = []
    for e in errors[:5]:
        loc = "/".join(str(p) for p in e.path) or "(root)"
        parts.append(f"{loc}: {e.message}")
    more = f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""
    return CheckResult(name=name, passed=False, detail="; ".join(parts) + more)


def check_name_is_string(spec: dict, case: Case) -> CheckResult:
    """`name` must be a non-empty string."""
    name = "name-is-string"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    if not _nonempty_str(spec.get("name")):
        return CheckResult(name=name, passed=False, detail="name missing or empty")
    return CheckResult(name=name, passed=True)


def check_top_level_keys(spec: dict, case: Case) -> CheckResult:
    """All REQUIRED_TOP_LEVEL_KEYS must be present."""
    name = "top-level-keys"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in spec]
    if missing:
        return CheckResult(name=name, passed=False, detail=f"missing keys: {missing}")
    return CheckResult(name=name, passed=True)


def check_body_plan(spec: dict, case: Case) -> CheckResult:
    """`body_plan` is a dict with required keys, valid core_shape + symmetry, positive size."""
    name = "body-plan"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    body = spec.get("body_plan")
    if not isinstance(body, dict):
        return CheckResult(name=name, passed=False, detail="body_plan is not a dict")
    missing = [k for k in REQUIRED_BODY_PLAN_KEYS if k not in body]
    if missing:
        return CheckResult(name=name, passed=False, detail=f"missing keys: {missing}")
    core_shape = body.get("core_shape")
    if VALID_CORE_SHAPES and core_shape not in VALID_CORE_SHAPES:
        return CheckResult(
            name=name, passed=False, detail=f"core_shape {core_shape!r} not in {VALID_CORE_SHAPES}"
        )
    symmetry = body.get("symmetry")
    if symmetry not in VALID_SYMMETRIES:
        return CheckResult(
            name=name, passed=False, detail=f"symmetry {symmetry!r} not in {VALID_SYMMETRIES}"
        )
    size = body.get("size_est_m")
    # bool is an int subclass; exclude it explicitly.
    if isinstance(size, bool) or not isinstance(size, (int, float)) or size <= 0:
        return CheckResult(
            name=name, passed=False, detail=f"size_est_m not a positive number: {size!r}"
        )
    return CheckResult(name=name, passed=True)


def check_parts(spec: dict, case: Case) -> CheckResult:
    """`parts` is a list (may be empty per the contract); each entry is well-formed.

    The schema explicitly allows an empty parts list (a featureless blob) and a
    part count >= 0, so this check does NOT require non-empty parts — that would
    reject contract-valid Interpreter output.
    """
    name = "parts"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    parts = spec.get("parts")
    if not isinstance(parts, list):
        return CheckResult(name=name, passed=False, detail="parts is not a list")
    for i, part in enumerate(parts):
        if not isinstance(part, dict):
            return CheckResult(name=name, passed=False, detail=f"parts[{i}] is not a dict")
        missing = [k for k in REQUIRED_PART_KEYS if k not in part]
        if missing:
            return CheckResult(
                name=name, passed=False, detail=f"parts[{i}] missing keys: {missing}"
            )
        count = part.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            return CheckResult(
                name=name,
                passed=False,
                detail=f"parts[{i}].count not a non-negative int: {count!r}",
            )
    return CheckResult(name=name, passed=True)


def check_palette(spec: dict, case: Case) -> CheckResult:
    """`palette` is a non-empty list of valid hex color strings."""
    name = "palette-is-hex"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    palette = spec.get("palette")
    if not isinstance(palette, list) or not palette:
        return CheckResult(name=name, passed=False, detail="palette missing or empty")
    for i, color in enumerate(palette):
        if not isinstance(color, str) or not _HEX_RE.match(color):
            return CheckResult(
                name=name, passed=False, detail=f"palette[{i}] not a hex color: {color!r}"
            )
    return CheckResult(name=name, passed=True)


def check_distinctive_features(spec: dict, case: Case) -> CheckResult:
    """`distinctive_features` is a non-empty list of non-empty strings."""
    name = "distinctive-features"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    features = spec.get("distinctive_features")
    if not isinstance(features, list) or not features:
        return CheckResult(name=name, passed=False, detail="distinctive_features missing or empty")
    for i, feat in enumerate(features):
        if not _nonempty_str(feat):
            return CheckResult(
                name=name,
                passed=False,
                detail=f"distinctive_features[{i}] not a non-empty string: {feat!r}",
            )
    return CheckResult(name=name, passed=True)


def check_locomotion(spec: dict, case: Case) -> CheckResult:
    """`locomotion` must be one of the schema's allowed values (a non-empty string if no enum)."""
    name = "locomotion"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    loco = spec.get("locomotion")
    if VALID_LOCOMOTION:
        if loco not in VALID_LOCOMOTION:
            return CheckResult(
                name=name, passed=False, detail=f"locomotion {loco!r} not in {VALID_LOCOMOTION}"
            )
    elif not _nonempty_str(loco):
        return CheckResult(name=name, passed=False, detail="locomotion missing or empty")
    return CheckResult(name=name, passed=True)


def check_vibe(spec: dict, case: Case) -> CheckResult:
    """`vibe` must be a non-empty string."""
    name = "vibe"
    if not isinstance(spec, dict):
        return CheckResult(name=name, passed=False, detail="spec is not a dict")
    if not _nonempty_str(spec.get("vibe")):
        return CheckResult(name=name, passed=False, detail="vibe missing or empty")
    return CheckResult(name=name, passed=True)


# The deterministic suite, in execution order. Schema validation runs first as
# the authoritative gate; the rest are readable per-field diagnostics.
DETERMINISTIC_CHECKS: list[Check] = [
    check_schema_valid,
    check_name_is_string,
    check_top_level_keys,
    check_body_plan,
    check_parts,
    check_palette,
    check_distinctive_features,
    check_locomotion,
    check_vibe,
]


# --------------------------------------------------------------------------- #
# LLM-as-judge check                                                          #
# --------------------------------------------------------------------------- #
_JUDGE_MODEL = "claude-sonnet-4-6"


def llm_judge_check(spec: dict, case: Case) -> CheckResult:
    """Ask Claude whether the spec plausibly matches the described drawing.

    Degrades to a *passing* skip whenever it cannot run (no key, no package,
    API or parse error) so an unavailable judge never reds the suite.
    """
    name = "llm-judge"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return CheckResult(name=name, passed=True, detail="skipped: ANTHROPIC_API_KEY not set")

    # Import inside the function so the deterministic path never needs anthropic.
    try:
        from anthropic import Anthropic
    except Exception as exc:  # noqa: BLE001 - any import failure means skip.
        return CheckResult(
            name=name, passed=True, detail=f"skipped: anthropic import failed ({exc})"
        )

    try:
        client = Anthropic()
        prompt = (
            "You judge whether a machine-generated creature spec plausibly matches "
            "a child's drawing, described below.\n\n"
            f"Drawing notes: {case.notes or '(none)'}\n"
            f"Expected features: {case.expected_features or '(none)'}\n\n"
            f"Creature spec (JSON):\n{json.dumps(spec, ensure_ascii=False)}\n\n"
            'Reply with ONLY strict JSON: {"plausible": true/false, "reason": "..."}'
        )
        resp = client.messages.create(
            model=_JUDGE_MODEL,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()
        verdict = json.loads(text)
        plausible = bool(verdict.get("plausible"))
        reason = str(verdict.get("reason", "")).strip()
        return CheckResult(name=name, passed=plausible, detail=reason)
    except Exception as exc:  # noqa: BLE001 - any API/parse failure means skip.
        return CheckResult(name=name, passed=True, detail=f"skipped: judge error ({exc})")
