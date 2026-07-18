"""Fill the field-guide HTML template. Coordinator fills named slots; it never
freehands markup. All media is inlined (base64) so the page is one portable file.
"""

import base64
import html as html_lib
import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

# The template already titles each section with an <h2>. A section that also
# opens with its own top-level <h1> renders the title twice, so strip a single
# leading <h1> from each section body.
_LEADING_H1 = re.compile(r"\A\s*<h1\b[^>]*>.*?</h1>\s*", re.IGNORECASE | re.DOTALL)


def _strip_leading_title(section_html: str) -> str:
    return _LEADING_H1.sub("", section_html, count=1)

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
            f'style="width:100%;height:480px;background:var(--stage,#f4f4f4)"></model-viewer>'
        )
    else:
        model_viewer = '<p class="missing">3D model not available.</p>'

    if video_path:
        # The animator (walk-cycle-anim) emits a self-contained HTML/canvas block,
        # NOT an .mp4 — the {{video}} slot receives markup, not a <video> tag
        # (design doc, Contract 2). It ships its own <head>/CSS/classes, so we
        # isolate it in an iframe rather than inlining the raw markup (which would
        # leak styles into the field guide). Inlined as a data URI to keep the page
        # a single portable file, consistent with every other asset here.
        walk_uri = _data_uri(video_path, "text/html")
        video = (
            f'<iframe src="{walk_uri}" title="walk cycle" loading="lazy" '
            f'style="width:100%;height:520px;border:0;background:transparent"></iframe>'
        )
    else:
        video = '<p class="missing">Walk-cycle animation not available.</p>'

    slots = {
        "creature_name": html_lib.escape(creature_name),
        "tagline": html_lib.escape(tagline),
        "doodle_img": _img_data_uri(doodle_path),
        "model_viewer": model_viewer,
        "video": video,
        "biology_html": _strip_leading_title(biology_html),
        "habitat_html": _strip_leading_title(habitat_html),
        "society_html": _strip_leading_title(society_html),
    }
    out = template
    for key, value in slots.items():
        out = out.replace("{{" + key + "}}", value)
    return out
