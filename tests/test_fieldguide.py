from pathlib import Path

from tests.conftest import load_module_from_path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "fieldguide-html"
render = load_module_from_path("render", SKILL / "render.py")


def _doodle(tmp_path):
    p = tmp_path / "d.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake")
    return str(p)


def _glb(tmp_path):
    p = tmp_path / "c.glb"
    p.write_bytes(b"glTF-fake")
    return str(p)


def _walk_cycle(tmp_path):
    # The animator emits a self-contained HTML document, not an .mp4.
    p = tmp_path / "walk-cycle.html"
    p.write_text("<!doctype html><html><body><div class='wc-stage'>walk</div></body></html>")
    return str(p)


def _base(tmp_path, **over):
    args = {
        "creature_name": "Test Blob",
        "tagline": "an earnest waddler",
        "doodle_path": _doodle(tmp_path),
        "biology_html": "<p>bio</p>",
        "habitat_html": "<p>hab</p>",
        "society_html": "<p>soc</p>",
    }
    args.update(over)
    return args


def test_all_slots_filled(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=_glb(tmp_path)))
    assert "Test Blob" in html
    assert "<model-viewer" in html
    assert "{{" not in html  # no leftover placeholders


def test_missing_glb_degrades(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=None))
    # Assert the ELEMENT is gone, not the bare string: the stylesheet names
    # model-viewer in a selector and a comment, so a substring check matches the CSS
    # and fails while the degrade path is working perfectly.
    assert "<model-viewer" not in html
    assert "not available" in html
    assert "{{" not in html


def test_missing_video_omitted(tmp_path):
    html = render.render_field_guide(**_base(tmp_path, glb_path=_glb(tmp_path)))
    assert "<video" not in html
    assert "not available" in html  # the {{video}} slot degrades gracefully
    assert "{{" not in html


def test_walk_cycle_embedded_as_iframe(tmp_path):
    # The animator's walk-cycle.html must land in the {{video}} slot as an
    # isolated iframe — never wrapped in a <video> tag (design doc, Contract 2).
    html = render.render_field_guide(
        **_base(tmp_path, glb_path=_glb(tmp_path), video_path=_walk_cycle(tmp_path))
    )
    assert "<iframe" in html
    assert "data:text/html" in html
    assert "<video" not in html  # regression guard: was <video src=video/mp4>
    assert "video/mp4" not in html
    assert "{{" not in html
