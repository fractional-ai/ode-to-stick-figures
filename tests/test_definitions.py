from agents import definitions as d


def test_specialists_have_required_keys():
    keys = {s["key"] for s in d.SPECIALISTS}
    assert {"biologist", "habitat", "society", "modeler_3d"} <= keys
    for s in d.SPECIALISTS:
        assert s["name"] and s["model"] and s["system"]


def test_interpreter_defined():
    assert d.INTERPRETER["key"] == "field_interpreter"
    assert "spec" in d.INTERPRETER["system"].lower()


def test_interpreter_prompt_demands_literal_transcription():
    system = d.INTERPRETER["system"].lower()
    # The governing rule: be literal about the drawing, don't invent anatomy.
    assert "literal" in system
    assert "doodle" in system
    # It must commit to a specific reading rather than hedge on ambiguity.
    assert "committed" in system or "commit" in system
    # And it must name the schema every downstream specialist builds from.
    assert "creature-spec.schema.json" in system


def test_coordinator_prompt_mentions_all_lanes():
    text = d.COORDINATOR_SYSTEM.lower()
    for word in ("biolog", "habitat", "society", "3d", "fieldguide"):
        assert word in text
