---
name: fieldguide-html
description: Assemble the final self-contained HTML field-guide page from the specialists' sections and artifacts, using the bundled renderer and template. Use when producing the final creature field guide deliverable.
---

# Field Guide HTML

You have `render.py` and `template.html` in this skill. Collect the specialists'
markdown sections (convert to HTML), the original doodle, and `creature.glb`
(and the walk-cycle video if present), then call:

    import render
    html = render.render_field_guide(
        creature_name=..., tagline=..., doodle_path="doodle.png",
        biology_html=..., habitat_html=..., society_html=...,
        glb_path="creature.glb",        # or None
        video_path="walk-cycle.mp4",    # or None
    )
    open("field-guide.html", "w").write(html)

Never freehand HTML — only fill the template's slots. Missing `glb_path` or
`video_path` degrades gracefully. The deliverable is `field-guide.html`.
