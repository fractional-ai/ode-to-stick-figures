from types import SimpleNamespace

from upload_skills import _skill_id_of


def test_skill_id_of_dict():
    assert _skill_id_of({"skill_id": "skill_abc", "type": "custom"}) == "skill_abc"


def test_skill_id_of_model_object():
    obj = SimpleNamespace(skill_id="skill_xyz", type="custom")
    assert _skill_id_of(obj) == "skill_xyz"
