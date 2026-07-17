from agents import definitions as d


def test_specialists_have_required_keys():
    keys = {s["key"] for s in d.SPECIALISTS}
    assert {"biologist", "habitat", "society", "modeler"} <= keys
    for s in d.SPECIALISTS:
        assert s["name"] and s["model"] and s["system"]


def test_interpreter_defined():
    assert d.INTERPRETER["key"] == "interpreter"
    assert "spec" in d.INTERPRETER["system"].lower()


def test_coordinator_prompt_mentions_all_lanes():
    text = d.COORDINATOR_SYSTEM.lower()
    for word in ("biolog", "habitat", "society", "3d", "field-guide"):
        assert word in text
