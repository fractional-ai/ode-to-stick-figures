"""Fill the field-guide HTML template. Coordinator fills named slots; it never
freehands markup. All media is inlined (base64) so the page is one portable file.
"""

import base64
import html as html_lib
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

MODEL_VIEWER_CDN = "https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"


def _data_uri(path: str, mime: str) -> str:
    b64 = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def _img_data_uri(path: str) -> str:
    ext = Path(path).suffix.lstrip(".").lower() or "png"
    return _data_uri(path, f"image/{ext}")


def render_field_guide(*, creature_name, tagline, doodle_path,
                       biology_html, habitat_html, society_html,
                       glb_path=None, video_path=None,
                       template_path=TEMPLATE_PATH) -> str:
    template = Path(template_path).read_text()

    if glb_path:
        glb_uri = _data_uri(glb_path, "model/gltf-binary")
        model_viewer = (
            f'<script type="module" src="{MODEL_VIEWER_CDN}"></script>'
            f'<model-viewer src="{glb_uri}" camera-controls auto-rotate '
            f'style="width:100%;height:480px;background:#f4f4f4"></model-viewer>'
        )
    else:
        model_viewer = '<p class="missing">3D model not available.</p>'

    if video_path:
        video_uri = _data_uri(video_path, "video/mp4")
        video = f'<video controls loop src="{video_uri}" style="width:100%"></video>'
    else:
        video = '<p class="missing">Walk-cycle video not available.</p>'

    slots = {
        "creature_name": html_lib.escape(creature_name),
        "tagline": html_lib.escape(tagline),
        "doodle_img": _img_data_uri(doodle_path),
        "model_viewer": model_viewer,
        "video": video,
        "biology_html": biology_html,
        "habitat_html": habitat_html,
        "society_html": society_html,
    }
    out = template
    for key, value in slots.items():
        out = out.replace("{{" + key + "}}", value)
    return out
