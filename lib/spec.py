"""Load and validate a Creature Spec against the shared contract schema.

The Creature Spec is the consistency seam: the Field Interpreter emits it and
every downstream specialist consumes it. Validating here keeps a specialist
from silently working off a malformed spec.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "contracts" / "creature-spec.schema.json"


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    return json.loads(Path(schema_path).read_text())


def validate_spec(spec: dict, schema_path: Path = SCHEMA_PATH) -> dict:
    validator = Draft202012Validator(load_schema(schema_path))
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{list(e.path) or '<root>'}: {e.message}" for e in errors)
        raise ValueError(f"Invalid creature spec: {detail}")
    return spec


def load_spec(path, schema_path: Path = SCHEMA_PATH) -> dict:
    spec = json.loads(Path(path).read_text())
    return validate_spec(spec, schema_path)
