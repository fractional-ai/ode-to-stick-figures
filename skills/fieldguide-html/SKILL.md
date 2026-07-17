---
name: fieldguide-html
description: Assemble the final field-guide.html page by filling the named slots in template.html. Used by the coordinator only — never by a specialist. Never freehand markup outside the template's slots.
---

# Field Guide HTML

Use this skill to assemble the final deliverable: one self-contained
`field-guide.html` file, all assets inlined as base64.

## Inputs

- `creature_name`, `tagline` — short strings
- `doodle_img` — the original doodle, inlined as a `data:` URI
- `biology_html`, `habitat_html`, `society_html` — markdown from the
  Biologist/Habitat/Society specialists, rendered to HTML fragments
- `creature.glb` (optional) — if present, render `{{model_viewer}}` as
  `<model-viewer src="data:...">`; if absent, leave the slot empty
- `walk-cycle.mp4` (optional, stretch) — if present, render `{{video}}` as
  a `<video>` block; if absent, leave the slot empty

## Rules

1. Load `template.html` from this skill's directory. Fill only the named
   `{{slot}}` placeholders — never add or restructure markup around them.
2. All binary assets (doodle, glb, mp4) must be inlined as base64 `data:`
   URIs so the output is a single portable file with no external
   references except the model-viewer CDN script tag already in the
   template.
3. Graceful degradation: a missing `.glb` or `.mp4` must still produce a
   valid page — omit the slot's content, don't fail the whole build.
4. Write the result to `field-guide.html` in the working directory.

## Non-negotiables

- This skill belongs to the coordinator only. Specialists never call it.
- Never contradict the Creature Spec when filling `creature_name`/`tagline`.

TODO (owner): write the actual slot-filling script (markdown->HTML for the
three prose sections, base64 inlining for the binary slots) and wire it in
here as a runnable snippet, per the design doc's per-lane standalone-testing
requirement.
