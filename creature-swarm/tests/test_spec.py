import json
from pathlib import Path

import pytest

import lib.spec as spec_mod

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
EXAMPLE = CONTRACTS / "creature-spec.example.json"


def test_example_validates():
    data = json.loads(EXAMPLE.read_text())
    assert spec_mod.validate_spec(data) is data


def test_load_spec_returns_dict():
    loaded = spec_mod.load_spec(EXAMPLE)
    assert loaded["name"]
    assert "body_plan" in loaded
    assert isinstance(loaded["parts"], list)


def test_invalid_spec_raises():
    broken = {"name": "x"}  # missing required body_plan/parts/etc.
    with pytest.raises(ValueError):
        spec_mod.validate_spec(broken)
