from agents import definitions as d


def test_specialists_have_required_keys():
    keys = {s["key"] for s in d.SPECIALISTS}
    assert {"biologist", "habitat", "society", "modeler"} <= keys
    for s in d.SPECIALISTS:
        assert s["name"] and s["model"] and s["system"]


def test_interpreter_defined():
    assert d.INTERPRETER["key"] == "interpreter"
    assert "spec" in d.INTERPRETER["system"].lower()


def test_interpreter_prompt_demands_literal_transcription():
    system = d.INTERPRETER["system"].lower()
    # The governing rule: transcribe what's actually drawn, don't genericize it away.
    assert "literal" in system
    assert "shark" in system and "dog" in system  # the canonical example case
    # Never bail on weird/ambiguous input — always produce a full spec.
    assert "never refuse" in system or "always commit" in system


def test_coordinator_prompt_mentions_all_lanes():
    text = d.COORDINATOR_SYSTEM.lower()
    for word in ("biolog", "habitat", "society", "3d", "field-guide"):
        assert word in text
