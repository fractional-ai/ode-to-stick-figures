import base64
import importlib.util
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "fieldguide-html"
_spec = importlib.util.spec_from_file_location("render", SKILL / "render.py")
render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render)


def _doodle(tmp_path):
    p = tmp_path / "d.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake")
    return str(p)


def _glb(tmp_path):
    p = tmp_path / "c.glb"
    p.write_bytes(b"glTF-fake")
    return str(p)


def _base(tmp_path, **over):
    args = dict(
        creature_name="Test Blob", tagline="an earnest waddler",
        doodle_path=_doodle(tmp_path),
        biology_html="<p>bio</p>", habitat_html="<p>hab</p>", society_html="<p>soc</p>",
    )
    args.update(over)
    return args


def test_all_slots_filled(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=_glb(tmp_path)))
    assert "Test Blob" in html
    assert "model-viewer" in html
    assert "{{" not in html  # no leftover placeholders


def test_missing_glb_degrades(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=None))
    assert "model-viewer" not in html
    assert "not available" in html
    assert "{{" not in html


def test_missing_video_omitted(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=_glb(tmp_path)))
    assert "<video" not in html
    assert "{{" not in html
