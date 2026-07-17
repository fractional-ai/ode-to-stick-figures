# Creature Swarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a swarm that takes a bad drawing of a made-up animal and produces a self-contained HTML "field guide" — biology, habitat, society writeups plus an interactive procedural 3D model — built on Claude Managed Agents.

**Architecture:** A coordinator agent fans work out to specialist sub-agents on Claude Managed Agents (multi-agent). A vision Field Interpreter turns the doodle into a canonical Creature Spec (the consistency contract); the coordinator fans that Spec to Biologist, Habitat, Society, and a procedural 3D Modeler in parallel, then assembles everything into one portable HTML page via a `fieldguide-html` skill. Deterministic logic (spec validation, 3D build, HTML render) lives in plain Python modules that are unit-tested locally and also shipped inside the relevant skills; the API scripts only orchestrate.

**Tech Stack:** Python 3.11+, `anthropic` SDK (managed-agents preview), `trimesh` (procedural 3D → glb), `ffmpeg` (stretch video), `jsonschema` (spec validation), `<model-viewer>` web component (in-browser 3D).

## Global Constraints

- Python 3.11+.
- `anthropic` SDK: pin a version that includes `client.beta.agents`, `client.beta.sessions`, `client.beta.skills`, `client.beta.environments`, and `anthropic.lib.files_from_dir` (managed-agents preview). Do NOT use `anthropic>=0.40.0` — that floor predates these APIs. Pin the exact version the team confirms works during Task 13.
- Managed-agents beta header string: `managed-agents-2026-04-01` (confirm current value against the console before the live run; it is defined once in `lib/client.py` and imported everywhere).
- Every script that calls a `client.beta.*` managed-agents endpoint MUST use the shared client from `lib/client.py` so the beta header is always present. (The original workshop repo set the header on only 3 of 7 scripts — do not repeat that.)
- The full run order is: `setup_environment.py` → `create_specialists.py` → `upload_skills.py` → `create_coordinator.py` → `run_creature_swarm.py`. `setup_environment.py` is part of the flow from the start and appears in the README and in every "run X first" error message.
- The Creature Spec contract lives at `creature-swarm/contracts/creature-spec.schema.json` with an example at `creature-swarm/contracts/creature-spec.example.json`. These are produced by a separate merged PR and are treated here as read-only inputs. Do not redefine the schema; consume it.
- Model IDs are configurable in `agents/definitions.py`. Defaults: coordinator `claude-opus-4-8`, specialists + interpreter `claude-sonnet-5`. Confirm these are enabled in the workspace before the live run.
- Every skill bundle has a `SKILL.md` at its root with YAML frontmatter containing `name` and `description`.
- All artifacts in the final HTML page are inlined (base64) so the page is a single portable file.

---

## File Structure

```
creature-swarm/
  README.md                    # setup + full run order + demo notes
  requirements.txt
  .env.example                 # ANTHROPIC_API_KEY=...
  contracts/                   # READ-ONLY input from the Creature Spec PR
    creature-spec.schema.json
    creature-spec.example.json
    README.md
  lib/
    __init__.py
    client.py                  # managed_client() + MANAGED_AGENTS_BETA constant
    spec.py                    # load/validate a Creature Spec against the schema
  agents/
    __init__.py
    definitions.py             # SPECIALISTS list + COORDINATOR + INTERPRETER prompts/config (pure data)
  create_specialists.py
  create_coordinator.py
  upload_skills.py
  setup_environment.py
  run_creature_swarm.py
  download_deliverable.py
  skills/
    creature-biology/SKILL.md
    habitat-ecology/SKILL.md
    folklore-society/SKILL.md            # owner's discretion: prompt-only is also valid
    procedural-creature-3d/
      SKILL.md
      build.py                 # build_creature / build_creature_glb (trimesh)
    fieldguide-html/
      SKILL.md
      template.html            # named {{slots}}
      render.py                # render_field_guide(...)
    walk-cycle-anim/
      SKILL.md                 # STUB — handoff contract only, no working code
  tests/
    __init__.py
    test_spec.py
    test_creature3d.py
    test_fieldguide.py
  synthetic-data/
    doodle-example.png
```

---

## Task 1: Scaffold folder, requirements, and the shared managed-agents client

**Files:**
- Create: `creature-swarm/requirements.txt`
- Create: `creature-swarm/.env.example`
- Create: `creature-swarm/lib/__init__.py` (empty)
- Create: `creature-swarm/tests/__init__.py` (empty)
- Create: `creature-swarm/lib/client.py`
- Test: `creature-swarm/tests/test_client.py`

**Interfaces:**
- Produces: `lib.client.MANAGED_AGENTS_BETA: str`; `lib.client.managed_client() -> anthropic.Anthropic` (an `Anthropic` client with the managed-agents beta header set and API key from env).

- [ ] **Step 1: Write `requirements.txt`**

```
anthropic
python-dotenv>=1.0.0
trimesh>=4.0.0
numpy>=1.24.0
jsonschema>=4.20.0
```

(Leave `anthropic` unpinned for now; Task 13 pins the confirmed working version.)

- [ ] **Step 2: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 3: Write the failing test** `creature-swarm/tests/test_client.py`

```python
import lib.client as client_mod


def test_beta_constant_present():
    assert isinstance(client_mod.MANAGED_AGENTS_BETA, str)
    assert client_mod.MANAGED_AGENTS_BETA


def test_managed_client_sets_beta_header(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    c = client_mod.managed_client()
    # The beta header must be on the client so every beta.* call carries it.
    headers = c._client.headers if hasattr(c, "_client") else c.default_headers
    joined = " ".join(f"{k}:{v}" for k, v in dict(headers).items())
    assert client_mod.MANAGED_AGENTS_BETA in joined


def test_managed_client_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        client_mod.managed_client()
        assert False, "expected SystemExit"
    except SystemExit:
        pass
```

- [ ] **Step 4: Run it, verify it fails**

Run: `cd creature-swarm && python -m pytest tests/test_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'lib.client'`).

- [ ] **Step 5: Implement `lib/client.py`**

```python
"""Shared Anthropic client for the managed-agents preview.

Defined once so the beta header is present on every beta.* call. The original
workshop repo set this header on only some scripts, which fails silently
against the preview endpoints.
"""

import os

from anthropic import Anthropic

MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


def managed_client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")
    return Anthropic(
        api_key=api_key,
        default_headers={"anthropic-beta": MANAGED_AGENTS_BETA},
    )
```

- [ ] **Step 6: Run it, verify it passes**

Run: `cd creature-swarm && python -m pytest tests/test_client.py -v`
Expected: PASS (3 tests). If the header assertion fails due to SDK internals, adjust the test to read `c.default_headers` — the implementation is correct as long as the header is passed to `Anthropic(...)`.

- [ ] **Step 7: Commit**

```bash
git add creature-swarm/requirements.txt creature-swarm/.env.example creature-swarm/lib creature-swarm/tests
git commit -m "feat(creature-swarm): scaffold + shared managed-agents client"
```

---

## Task 2: Creature Spec loader + validator

**Files:**
- Create: `creature-swarm/lib/spec.py`
- Test: `creature-swarm/tests/test_spec.py`

**Interfaces:**
- Consumes: `creature-swarm/contracts/creature-spec.schema.json` and `contracts/creature-spec.example.json` (read-only, from the merged Creature Spec PR).
- Produces: `lib.spec.load_schema(schema_path=...) -> dict`; `lib.spec.validate_spec(spec: dict, schema_path=...) -> dict` (returns the spec, raises `ValueError` on invalid); `lib.spec.load_spec(path, schema_path=...) -> dict`.

- [ ] **Step 1: Confirm the contract is present**

Run: `ls creature-swarm/contracts/creature-spec.schema.json creature-swarm/contracts/creature-spec.example.json`
Expected: both files listed. If missing, STOP — the Creature Spec PR has not merged yet; pull `main` first.

- [ ] **Step 2: Write the failing test** `creature-swarm/tests/test_spec.py`

```python
import json
from pathlib import Path

import pytest

import lib.spec as spec_mod

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
EXAMPLE = CONTRACTS / "creature-spec.example.json"


def test_example_validates():
    data = json.loads(EXAMPLE.read_text())
    assert spec_mod.validate_spec(data) is data


def test_load_spec_returns_dict():
    loaded = spec_mod.load_spec(EXAMPLE)
    assert loaded["name"]
    assert "body_plan" in loaded
    assert isinstance(loaded["parts"], list)


def test_invalid_spec_raises():
    broken = {"name": "x"}  # missing required body_plan/parts/etc.
    with pytest.raises(ValueError):
        spec_mod.validate_spec(broken)
```

- [ ] **Step 3: Run it, verify it fails**

Run: `cd creature-swarm && python -m pytest tests/test_spec.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'lib.spec'`).

- [ ] **Step 4: Implement `lib/spec.py`**

```python
"""Load and validate a Creature Spec against the shared contract schema.

The Creature Spec is the consistency seam: the Field Interpreter emits it and
every downstream specialist consumes it. Validating here keeps a specialist
from silently working off a malformed spec.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "contracts" / "creature-spec.schema.json"


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    return json.loads(Path(schema_path).read_text())


def validate_spec(spec: dict, schema_path: Path = SCHEMA_PATH) -> dict:
    validator = Draft202012Validator(load_schema(schema_path))
    errors = sorted(validator.iter_errors(spec), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{list(e.path) or '<root>'}: {e.message}" for e in errors)
        raise ValueError(f"Invalid creature spec: {detail}")
    return spec


def load_spec(path, schema_path: Path = SCHEMA_PATH) -> dict:
    spec = json.loads(Path(path).read_text())
    return validate_spec(spec, schema_path)
```

- [ ] **Step 5: Run it, verify it passes**

Run: `cd creature-swarm && python -m pytest tests/test_spec.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add creature-swarm/lib/spec.py creature-swarm/tests/test_spec.py
git commit -m "feat(creature-swarm): creature spec loader + validator"
```

---

## Task 3: Procedural 3D builder

**Files:**
- Create: `creature-swarm/skills/procedural-creature-3d/build.py`
- Test: `creature-swarm/tests/test_creature3d.py`

**Interfaces:**
- Consumes: a validated Creature Spec dict (Task 2 shape); `trimesh`, `numpy`.
- Produces: `build.build_creature(spec: dict) -> trimesh.Scene`; `build.build_creature_glb(spec: dict, out_path: str) -> str` (writes a `.glb`, returns `out_path`).

- [ ] **Step 1: Write the failing test** `creature-swarm/tests/test_creature3d.py`

```python
import json
from pathlib import Path

import trimesh

import importlib.util

BUILD = Path(__file__).resolve().parents[1] / "skills" / "procedural-creature-3d" / "build.py"
_spec = importlib.util.spec_from_file_location("build", BUILD)
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)

SPEC = {
    "name": "Test Blob",
    "body_plan": {"core_shape": "sphere", "symmetry": "radial", "size_est_m": 0.5},
    "parts": [{"type": "leg", "count": 6, "shape": "cylinder", "placement": "underside"}],
    "palette": ["#33aa55", "#224466"],
    "distinctive_features": ["nubbly"],
    "locomotion": "waddle",
    "vibe": "earnest",
}


def test_build_creature_returns_scene_with_geometry():
    scene = build.build_creature(SPEC)
    assert isinstance(scene, trimesh.Scene)
    assert len(scene.geometry) >= 1


def test_part_count_reflected_in_geometry():
    scene = build.build_creature(SPEC)
    leg_nodes = [name for name in scene.geometry if name.startswith("leg")]
    assert len(leg_nodes) >= 6


def test_build_glb_writes_loadable_file(tmp_path):
    out = tmp_path / "creature.glb"
    result = build.build_creature_glb(SPEC, str(out))
    assert result == str(out)
    assert out.exists() and out.stat().st_size > 0
    reloaded = trimesh.load(str(out))
    assert reloaded is not None
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd creature-swarm && python -m pytest tests/test_creature3d.py -v`
Expected: FAIL (cannot load `build.py` — file does not exist).

- [ ] **Step 3: Implement `skills/procedural-creature-3d/build.py`**

```python
"""Build a deliberately lumpy 3D creature from a Creature Spec using trimesh.

The joke is a serious pipeline producing a crayon-faithful blob. Geometry is
composed from primitives keyed off body_plan/parts/palette. Exports .glb so
<model-viewer> can show it in the browser.
"""

import numpy as np
import trimesh


def _hex_to_rgba(hex_str: str):
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return [r, g, b, 255]


def _core_mesh(core_shape: str, size: float) -> trimesh.Trimesh:
    r = size / 2.0
    if core_shape == "ovoid":
        m = trimesh.creation.icosphere(radius=r)
        m.apply_scale([1.0, 0.8, 1.4])
        return m
    if core_shape == "slab":
        return trimesh.creation.box(extents=[size, size * 0.5, size * 1.2])
    # default + "sphere"
    return trimesh.creation.icosphere(radius=r)


def _ring_positions(count: int, radius: float, symmetry: str):
    """Return (x, z) offsets for `count` parts around the body."""
    if count <= 0:
        return []
    if symmetry == "bilateral":
        # split left/right, marched front-to-back
        positions = []
        per_side = max(1, count // 2)
        for i in range(count):
            side = -1 if i % 2 == 0 else 1
            row = i // 2
            z = (row - (per_side - 1) / 2.0) * (radius / max(1, per_side))
            positions.append((side * radius, z))
        return positions
    # radial
    return [
        (radius * np.cos(2 * np.pi * i / count), radius * np.sin(2 * np.pi * i / count))
        for i in range(count)
    ]


def _part_mesh(part_type: str, size: float) -> trimesh.Trimesh:
    if part_type in ("eyestalk", "antenna", "horn"):
        stalk = trimesh.creation.cylinder(radius=size * 0.04, height=size * 0.5)
        tip = trimesh.creation.icosphere(radius=size * 0.08)
        tip.apply_translation([0, 0, size * 0.25])
        return trimesh.util.concatenate([stalk, tip])
    if part_type in ("tail",):
        return trimesh.creation.capsule(radius=size * 0.08, height=size * 0.6)
    # default limb / leg
    return trimesh.creation.cylinder(radius=size * 0.07, height=size * 0.5)


def build_creature(spec: dict) -> trimesh.Scene:
    body_plan = spec["body_plan"]
    size = float(body_plan.get("size_est_m", 0.4))
    symmetry = body_plan.get("symmetry", "bilateral")
    palette = spec.get("palette") or ["#888888"]

    scene = trimesh.Scene()
    body = _core_mesh(body_plan["core_shape"], size)
    body.visual.face_colors = _hex_to_rgba(palette[0])
    scene.add_geometry(body, node_name="body")

    accent = _hex_to_rgba(palette[1] if len(palette) > 1 else palette[0])
    for i, part in enumerate(spec.get("parts", [])):
        ptype = part.get("type", "leg")
        count = int(part.get("count", 1))
        for j, (x, z) in enumerate(_ring_positions(count, size / 2.0, symmetry)):
            m = _part_mesh(ptype, size)
            m.visual.face_colors = accent
            # legs hang below; stalks/horns rise above; else radial on the body
            y = -size / 2.0 if ptype in ("leg", "limb") else size / 2.0
            m.apply_translation([x, y, z])
            scene.add_geometry(m, node_name=f"{ptype}_{i}_{j}")
    return scene


def build_creature_glb(spec: dict, out_path: str) -> str:
    scene = build_creature(spec)
    scene.export(out_path)  # extension (.glb) selects the exporter
    return out_path
```

- [ ] **Step 4: Run it, verify it passes**

Run: `cd creature-swarm && python -m pytest tests/test_creature3d.py -v`
Expected: PASS (3 tests). If `trimesh` glb export needs an extra dep, `pip install "trimesh[easy]"` and note it in requirements.

- [ ] **Step 5: Commit**

```bash
git add creature-swarm/skills/procedural-creature-3d/build.py creature-swarm/tests/test_creature3d.py
git commit -m "feat(creature-swarm): procedural 3D creature builder"
```

---

## Task 4: Field-guide HTML renderer + template

**Files:**
- Create: `creature-swarm/skills/fieldguide-html/template.html`
- Create: `creature-swarm/skills/fieldguide-html/render.py`
- Test: `creature-swarm/tests/test_fieldguide.py`

**Interfaces:**
- Consumes: rendered section HTML strings + artifact paths.
- Produces: `render.render_field_guide(*, creature_name, tagline, doodle_path, biology_html, habitat_html, society_html, glb_path=None, video_path=None, template_path=...) -> str`.

- [ ] **Step 1: Write `template.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Field Guide — {{creature_name}}</title>
<style>
  body { font-family: Georgia, serif; max-width: 820px; margin: 2rem auto; padding: 0 1rem; color:#222; }
  h1 { margin-bottom: .2rem; } .tagline { color:#666; font-style: italic; margin-top:0; }
  .doodle { max-width: 320px; border:1px solid #ccc; padding:8px; background:#fafafa; }
  section { margin: 1.6rem 0; } .missing { color:#999; font-style: italic; }
  h2 { border-bottom:2px solid #eee; padding-bottom:.2rem; }
</style>
</head>
<body>
  <h1>{{creature_name}}</h1>
  <p class="tagline">{{tagline}}</p>
  <img class="doodle" src="{{doodle_img}}" alt="original field sketch">
  <section><h2>Specimen</h2>{{model_viewer}}</section>
  <section><h2>In motion</h2>{{video}}</section>
  <section><h2>Biology</h2>{{biology_html}}</section>
  <section><h2>Habitat &amp; Ecology</h2>{{habitat_html}}</section>
  <section><h2>Folklore &amp; Society</h2>{{society_html}}</section>
</body>
</html>
```

- [ ] **Step 2: Write the failing test** `creature-swarm/tests/test_fieldguide.py`

```python
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
```

- [ ] **Step 3: Run it, verify it fails**

Run: `cd creature-swarm && python -m pytest tests/test_fieldguide.py -v`
Expected: FAIL (cannot load `render.py`).

- [ ] **Step 4: Implement `skills/fieldguide-html/render.py`**

```python
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
```

- [ ] **Step 5: Run it, verify it passes**

Run: `cd creature-swarm && python -m pytest tests/test_fieldguide.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add creature-swarm/skills/fieldguide-html/template.html creature-swarm/skills/fieldguide-html/render.py creature-swarm/tests/test_fieldguide.py
git commit -m "feat(creature-swarm): field-guide HTML renderer + template"
```

---

## Task 5: Author the specialist skills (SKILL.md files)

**Files:**
- Create: `creature-swarm/skills/creature-biology/SKILL.md`
- Create: `creature-swarm/skills/habitat-ecology/SKILL.md`
- Create: `creature-swarm/skills/folklore-society/SKILL.md`
- Create: `creature-swarm/skills/procedural-creature-3d/SKILL.md`
- Create: `creature-swarm/skills/fieldguide-html/SKILL.md`
- Create: `creature-swarm/skills/walk-cycle-anim/SKILL.md` (stub)

**Interfaces:**
- Produces: skill bundles that `upload_skills.py` (Task 9) uploads. Each has frontmatter `name` + `description`.

- [ ] **Step 1: Write `creature-biology/SKILL.md`**

```markdown
---
name: creature-biology
description: Invent rigorous, straight-faced biology for a made-up creature from its Creature Spec. Use when asked to describe anatomy, diet, life cycle, or physiology of a speculative animal.
---

# Creature Biology

You are handed a Creature Spec (JSON). Treat it as ground truth. Write a short,
authoritative biology section (200-300 words) as if for a real field guide.

Cover: body plan and what the anatomy implies, likely diet and metabolism,
reproduction/life cycle, and one genuinely surprising adaptation tied to a
`distinctive_features` entry. Cite the spec's features by name. Deadpan tone —
serious science about a silly animal. Output clean markdown, no preamble.
```

- [ ] **Step 2: Write `habitat-ecology/SKILL.md`**

```markdown
---
name: habitat-ecology
description: Describe the habitat and ecological niche of a made-up creature from its Creature Spec. Use when asked where a speculative animal lives, its range, climate, and ecosystem role.
---

# Habitat & Ecology

Given a Creature Spec (JSON), write a 200-300 word habitat and ecology section.

Cover: biome and climate that fit the body plan and `locomotion`, range and
microhabitat, its role in the food web (predators/prey), and one
ecological interaction that follows from a `distinctive_features` entry.
Consistent with the spec — do not invent traits that contradict it. Clean
markdown, no preamble.
```

- [ ] **Step 3: Write `folklore-society/SKILL.md`**

```markdown
---
name: folklore-society
description: Invent how a made-up creature interfaced with a made-up human society — myth, use, symbolism — from its Creature Spec. Use when asked about cultural or folkloric significance of a speculative animal.
---

# Folklore & Society

Given a Creature Spec (JSON), write a 200-300 word section on how a fictional
society related to this creature. Cover: what they called it and why, a myth or
superstition tied to a `distinctive_features` entry, any practical use
(labor, food, material), and its symbolism. Invent a plausible society; keep it
internally consistent with the creature's traits and `vibe`. Clean markdown.
```

Note (owner's discretion): this lane may run prompt-only instead of skill-backed.
If the owner chooses prompt-only, delete this directory and drop `folklore-society`
from `SKILL_TO_SPECIALIST` in Task 9. Both are valid; the Society specialist's
system prompt already carries the same brief.

- [ ] **Step 4: Write `procedural-creature-3d/SKILL.md`**

```markdown
---
name: procedural-creature-3d
description: Build a 3D model (.glb) of a made-up creature from its Creature Spec using the bundled trimesh builder. Use when asked to produce a 3D model, mesh, or glb of a speculative animal.
---

# Procedural Creature 3D

You have `build.py` in this skill. To produce the model, write the Creature Spec
to `spec.json` in the working directory, then run:

    pip install trimesh numpy
    python -c "import json, build; build.build_creature_glb(json.load(open('spec.json')), 'creature.glb')"

This emits `creature.glb`. Do not hand-author geometry — always use `build.py`
so the model stays consistent with the spec. Report the path to the coordinator.
```

- [ ] **Step 5: Write `fieldguide-html/SKILL.md`**

```markdown
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
```

- [ ] **Step 6: Write `walk-cycle-anim/SKILL.md` (STUB — handoff contract)**

```markdown
---
name: walk-cycle-anim
description: STUB — render a short walk-cycle video (.mp4) of a made-up creature. Not yet implemented. Handoff contract below.
---

# Walk-Cycle Animation (STUB — not implemented)

This skill is a stub for a separate owner to complete in their own session.

## Contract (do not change without updating the coordinator + fieldguide slot)
- Input: the Creature Spec (JSON) + `creature.glb` from the procedural-creature-3d skill.
- Output: `walk-cycle.mp4` in the working directory.
- Downstream: fills the `{{video}}` slot in the fieldguide-html template; that slot
  already degrades gracefully when the file is absent, so V1 runs fine without this.

## Suggested approach (for the implementer)
Reuse the primitive assembly from `procedural-creature-3d/build.py`; apply a
parametric per-leg phase offset keyed off `locomotion`; render N frames offscreen
and stitch with `ffmpeg` into `walk-cycle.mp4`. Depends only on `parts`/`locomotion`,
so it can rebuild from the spec even though the `.glb` is also available.

## Until implemented
Do not attach this skill to any agent. The Animator agent is out of V1 scope.
```

- [ ] **Step 7: Verify frontmatter on every skill**

Run:
```bash
cd creature-swarm && for f in skills/*/SKILL.md; do echo "== $f =="; head -4 "$f"; done
```
Expected: each shows `---`, `name:`, `description:`, `---`.

- [ ] **Step 8: Commit**

```bash
git add creature-swarm/skills
git commit -m "feat(creature-swarm): author specialist skills + animator stub"
```

---

## Task 6: Agent definitions (system prompts + roster config)

**Files:**
- Create: `creature-swarm/agents/__init__.py` (empty)
- Create: `creature-swarm/agents/definitions.py`
- Test: `creature-swarm/tests/test_definitions.py`

**Interfaces:**
- Produces: `agents.definitions.INTERPRETER: dict`; `agents.definitions.SPECIALISTS: list[dict]` (each `{key, name, model, system}`); `agents.definitions.COORDINATOR_SYSTEM: str`; `agents.definitions.MODELS: dict`.

- [ ] **Step 1: Write the failing test** `creature-swarm/tests/test_definitions.py`

```python
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
    for word in ("biolog", "habitat", "society", "3d", "field guide"):
        assert word in text
```

- [ ] **Step 2: Run it, verify it fails**

Run: `cd creature-swarm && python -m pytest tests/test_definitions.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'agents.definitions'`).

- [ ] **Step 3: Implement `agents/definitions.py`**

```python
"""Pure data: system prompts + model tiers for the creature swarm.

Kept separate from the API scripts so prompts are reviewable and testable
without touching the network.
"""

MODELS = {
    "coordinator": "claude-opus-4-8",
    "specialist": "claude-sonnet-5",
    "interpreter": "claude-sonnet-5",
}

INTERPRETER = {
    "key": "interpreter",
    "name": "Field Interpreter",
    "model": MODELS["interpreter"],
    "system": (
        "You are the Field Interpreter. You are given a child-like drawing of a "
        "made-up animal. Study it and emit a single Creature Spec as JSON — the "
        "canonical description every other specialist will build from.\n\n"
        "The spec MUST conform to the creature-spec schema: name, body_plan "
        "(core_shape, symmetry, size_est_m), parts (each with type, count, shape, "
        "placement), palette (hex colors you actually see), distinctive_features, "
        "locomotion, and a one-line vibe. Infer sensible structure from a messy "
        "drawing; commit to specifics so downstream agents stay consistent. "
        "Output ONLY the JSON object, nothing else."
    ),
}

SPECIALISTS = [
    {
        "key": "biologist",
        "name": "Creature Biologist",
        "model": MODELS["specialist"],
        "system": (
            "You are the Creature Biologist in a field-guide team. You receive a "
            "Creature Spec (JSON) and write a straight-faced 200-300 word biology "
            "section: anatomy, diet, life cycle, and one surprising adaptation tied "
            "to a distinctive feature. Treat the spec as ground truth. Use your "
            "creature-biology skill. Output clean markdown."
        ),
    },
    {
        "key": "habitat",
        "name": "Habitat Ecologist",
        "model": MODELS["specialist"],
        "system": (
            "You are the Habitat Ecologist. Given a Creature Spec (JSON), write a "
            "200-300 word habitat and ecology section: biome, range, food-web role, "
            "and one interaction that follows from a distinctive feature. Stay "
            "consistent with the spec. Use your habitat-ecology skill. Clean markdown."
        ),
    },
    {
        "key": "society",
        "name": "Folklore & Society Specialist",
        "model": MODELS["specialist"],
        "system": (
            "You are the Folklore & Society Specialist. Given a Creature Spec (JSON), "
            "write a 200-300 word section on how a fictional society related to this "
            "creature: name, myth, practical use, symbolism — all tied to its traits "
            "and vibe. Use your folklore-society skill if attached. Clean markdown."
        ),
    },
    {
        "key": "modeler",
        "name": "3D Modeler",
        "model": MODELS["specialist"],
        "system": (
            "You are the 3D Modeler. Given a Creature Spec (JSON), produce "
            "creature.glb using your procedural-creature-3d skill's build.py. Do not "
            "hand-author geometry. Report the path to the coordinator."
        ),
    },
]

COORDINATOR_SYSTEM = """\
You are the Field Editor running a creature field-guide desk. A bad drawing of a
made-up animal has arrived, already interpreted into a Creature Spec (JSON), which
you will be given.

# Your roster
- Creature Biologist: biology section
- Habitat Ecologist: habitat & ecology section
- Folklore & Society Specialist: society section
- 3D Modeler: produces creature.glb

# How to run the desk
1. Read the Creature Spec.
2. Delegate to ALL FOUR specialists in parallel. Give each the full Spec and a
   one-line brief. Ask the text specialists for ~250-word markdown sections.
3. When you have all four replies plus creature.glb, assemble the final
   deliverable with your fieldguide-html skill: fill the template slots with the
   sections, the original doodle, and creature.glb. Produce field-guide.html.
   The deliverable is the HTML file, not a chat message.

If the 3D model is missing, still produce the page — the template degrades
gracefully. Keep the tone of the writeups deadpan-serious about a silly animal.
"""
```

- [ ] **Step 4: Run it, verify it passes**

Run: `cd creature-swarm && python -m pytest tests/test_definitions.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add creature-swarm/agents creature-swarm/tests/test_definitions.py
git commit -m "feat(creature-swarm): agent definitions (prompts + model tiers)"
```

---

## Task 7: `setup_environment.py`

**Files:**
- Create: `creature-swarm/setup_environment.py`

**Interfaces:**
- Consumes: `lib.client.managed_client`.
- Produces: `.environment_id` file in `creature-swarm/`.

- [ ] **Step 1: Implement `setup_environment.py`**

```python
"""Create the cloud Environment the creature-swarm session runs in.

Idempotent — reuses .environment_id if present. Part of the standard run order:
setup_environment -> create_specialists -> upload_skills -> create_coordinator ->
run_creature_swarm.
"""

from pathlib import Path

from lib.client import managed_client


def main() -> None:
    env_path = Path(".environment_id")
    if env_path.exists():
        print(f"Environment already exists: {env_path.read_text().strip()}")
        print("(remove .environment_id to provision a new one)")
        return

    client = managed_client()
    environment = client.beta.environments.create(
        name="creature-swarm-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    env_path.write_text(environment.id)
    print(f"Environment created: {environment.id}")
    print("Next: python create_specialists.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify it imports and errors cleanly without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import setup_environment"`
Expected: no output, exit 0 (import must not call the API at import time).

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/setup_environment.py
git commit -m "feat(creature-swarm): environment setup (in run order from day one)"
```

---

## Task 8: `create_specialists.py`

**Files:**
- Create: `creature-swarm/create_specialists.py`

**Interfaces:**
- Consumes: `agents.definitions.INTERPRETER`, `agents.definitions.SPECIALISTS`, `lib.client.managed_client`.
- Produces: `.specialist_ids.json` mapping `{key: agent_id}` (includes `interpreter`).

- [ ] **Step 1: Implement `create_specialists.py`**

```python
"""Create the Field Interpreter + four specialist sub-agents.

Saves agent IDs to .specialist_ids.json for upload_skills.py and
create_coordinator.py.
"""

import json
from pathlib import Path

from agents.definitions import INTERPRETER, SPECIALISTS
from lib.client import managed_client

META = {"track": "creature-swarm"}


def _create(client, spec):
    agent = client.beta.agents.create(
        name=spec["name"],
        model=spec["model"],
        system=spec["system"],
        tools=[{"type": "agent_toolset_20260401"}],
        metadata={**META, "role": spec["key"]},
    )
    print(f"  Created {spec['name']:32s} -> {agent.id}")
    return agent.id


def main() -> None:
    client = managed_client()
    ids = {}
    for spec in [INTERPRETER, *SPECIALISTS]:
        ids[spec["key"]] = _create(client, spec)
    Path(".specialist_ids.json").write_text(json.dumps(ids, indent=2))
    print(f"\nSaved {len(ids)} agent IDs to .specialist_ids.json")
    print("Next: python upload_skills.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import create_specialists"`
Expected: exit 0, no API call at import.

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/create_specialists.py
git commit -m "feat(creature-swarm): create interpreter + specialist agents"
```

---

## Task 9: `upload_skills.py` (with the object-vs-dict fix)

**Files:**
- Create: `creature-swarm/upload_skills.py`

**Interfaces:**
- Consumes: `.specialist_ids.json`, the `skills/` bundles, `lib.client.managed_client`, `anthropic.lib.files_from_dir`.
- Produces: `.skill_ids.json`; attaches each skill to its specialist.

- [ ] **Step 1: Implement `upload_skills.py`**

```python
"""Upload each skill in skills/ and attach it to the matching specialist.

Idempotent: reuses a skill with the same display_title and skips a duplicate
attach. Handles retrieved skill entries whether the SDK returns dicts or model
objects (the original workshop repo assumed dicts and crashed on re-run).
"""

import json
from pathlib import Path

from anthropic.lib import files_from_dir

from lib.client import managed_client

# skill directory -> specialist key. (folklore-society is owner's discretion; drop
# this line if that lane runs prompt-only.)
SKILL_TO_SPECIALIST = {
    "creature-biology": "biologist",
    "habitat-ecology": "habitat",
    "folklore-society": "society",
    "procedural-creature-3d": "modeler",
    # fieldguide-html attaches to the coordinator (see create_coordinator.py),
    # not a specialist, so it is uploaded there.
}


def _skill_id_of(entry):
    """Read skill_id from a dict or a model object."""
    if isinstance(entry, dict):
        return entry.get("skill_id")
    return getattr(entry, "skill_id", None)


def main() -> None:
    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    client = managed_client()

    existing_by_title = {}
    for skill in client.beta.skills.list(source="custom"):
        existing_by_title[skill.display_title] = skill.id

    uploaded = {}
    for skill_name, specialist_key in SKILL_TO_SPECIALIST.items():
        skill_dir = Path("skills") / skill_name
        if not (skill_dir / "SKILL.md").exists():
            print(f"  Skipping {skill_name} — no SKILL.md")
            continue

        title = skill_name.replace("-", " ").title()
        if title in existing_by_title:
            skill_id = existing_by_title[title]
            print(f"Reusing skill {skill_name} ({skill_id})")
        else:
            print(f"Uploading skill {skill_name}...")
            skill = client.beta.skills.create(
                display_title=title, files=files_from_dir(str(skill_dir))
            )
            skill_id = skill.id
            print(f"  -> {skill_id}")
        uploaded[skill_name] = skill_id

        specialist_id = specialist_ids[specialist_key]
        current = client.beta.agents.retrieve(specialist_id)
        current_skills = list(current.skills or [])
        if any(_skill_id_of(s) == skill_id for s in current_skills):
            print(f"  already attached to {specialist_key} ✓")
            continue
        new_skills = [
            {"type": "custom", "skill_id": _skill_id_of(s), "version": "latest"}
            for s in current_skills
        ] + [{"type": "custom", "skill_id": skill_id, "version": "latest"}]
        client.beta.agents.update(
            specialist_id, version=current.version, skills=new_skills
        )
        print(f"  attached to {specialist_key} ✓")

    Path(".skill_ids.json").write_text(json.dumps(uploaded, indent=2))
    print(f"\nUploaded/attached {len(uploaded)} skills.")
    print("Next: python create_coordinator.py")


if __name__ == "__main__":
    main()
```

Note: this normalizes existing skills to dicts when rebuilding `new_skills`, so the
update payload is homogeneous regardless of what the SDK returned.

- [ ] **Step 2: Verify import without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import upload_skills"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/upload_skills.py
git commit -m "feat(creature-swarm): upload + attach skills (dict/object-safe)"
```

---

## Task 10: `create_coordinator.py`

**Files:**
- Create: `creature-swarm/create_coordinator.py`

**Interfaces:**
- Consumes: `.specialist_ids.json`, `agents.definitions.COORDINATOR_SYSTEM`, `agents.definitions.MODELS`, `lib.client.managed_client`, `anthropic.lib.files_from_dir`.
- Produces: `.coordinator_id` file; uploads + attaches the `fieldguide-html` skill to the coordinator.

- [ ] **Step 1: Implement `create_coordinator.py`**

```python
"""Create the coordinator ("Field Editor") whose roster is the four specialists.

Also uploads + attaches the fieldguide-html skill to the coordinator, since the
coordinator owns final assembly. The interpreter is NOT in the coordinator's
roster — it runs as a pre-step in run_creature_swarm.py (it needs the raw image).
"""

import json
from pathlib import Path

from anthropic.lib import files_from_dir

from agents.definitions import COORDINATOR_SYSTEM, MODELS
from lib.client import managed_client

SPECIALIST_ROSTER_KEYS = ["biologist", "habitat", "society", "modeler"]


def main() -> None:
    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py first.")
    specialist_ids = json.loads(ids_path.read_text())

    client = managed_client()

    # Upload + attach fieldguide-html to the coordinator.
    fg_dir = Path("skills/fieldguide-html")
    fg_skill = client.beta.skills.create(
        display_title="Fieldguide Html", files=files_from_dir(str(fg_dir))
    )

    roster = [{"type": "agent", "id": specialist_ids[k]} for k in SPECIALIST_ROSTER_KEYS]
    coordinator = client.beta.agents.create(
        name="Creature Field Editor",
        model=MODELS["coordinator"],
        system=COORDINATOR_SYSTEM,
        tools=[{"type": "agent_toolset_20260401"}],
        skills=[{"type": "custom", "skill_id": fg_skill.id, "version": "latest"}],
        multiagent={"type": "coordinator", "agents": roster},
        metadata={"track": "creature-swarm", "role": "coordinator"},
    )
    Path(".coordinator_id").write_text(coordinator.id)
    print(f"Coordinator created: {coordinator.id}")
    print(f"Roster: {SPECIALIST_ROSTER_KEYS}")
    print("Next: python setup_environment.py (if not done) then python run_creature_swarm.py")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import create_coordinator"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/create_coordinator.py
git commit -m "feat(creature-swarm): create coordinator + attach fieldguide skill"
```

---

## Task 11: `run_creature_swarm.py`

**Files:**
- Create: `creature-swarm/run_creature_swarm.py`

**Interfaces:**
- Consumes: `.coordinator_id`, `.specialist_ids.json`, `.environment_id`, `lib.client.managed_client`, a doodle image path (CLI arg, default `synthetic-data/doodle-example.png`).
- Produces: `outputs/field-guide.html` + any other artifacts the container produced; `outputs/creature-spec.json`; `.last_session_id`.

**Design note — interpreter as a pre-step:** the Field Interpreter runs in its own
session first, receiving the raw image, and returns the Creature Spec. The
coordinator session is then started with the Spec as text. This avoids depending on
the (unverified) ability to forward an image from a coordinator to a sub-agent, and
keeps the interpreter a distinct visible step. If Task 13 confirms images forward to
sub-agents, this can later move inside the coordinator's roster; the contract
(image in → Spec out → Spec fans to specialists) is unchanged.

- [ ] **Step 1: Implement `run_creature_swarm.py`**

```python
"""Run the creature swarm against a doodle.

Flow: Interpreter session (image -> Creature Spec) -> coordinator session (Spec ->
parallel specialists -> field-guide.html). Streams coordinator events so the
parallel fan-out is visible — that is the demo.

Usage:
    python run_creature_swarm.py [path/to/doodle.png]
"""

import base64
import json
import mimetypes
import sys
from pathlib import Path

from lib.client import managed_client
from lib.spec import validate_spec

OUTPUT_DIR = Path("outputs")
DEFAULT_DOODLE = Path("synthetic-data/doodle-example.png")


def _image_block(path: Path) -> dict:
    media_type = mimetypes.guess_type(str(path))[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def _require(*paths):
    for p in paths:
        if not Path(p).exists():
            raise SystemExit(
                f"Missing {p}. Run in order: setup_environment.py, "
                "create_specialists.py, upload_skills.py, create_coordinator.py."
            )


def interpret(client, environment_id, interpreter_id, doodle: Path) -> dict:
    print(f"\nInterpreting {doodle.name} -> Creature Spec...")
    session = client.beta.sessions.create(agent=interpreter_id, environment_id=environment_id,
                                          title="Creature interpretation")
    text = None
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [
                {"type": "text", "text": "Interpret this drawing into a Creature Spec JSON. Output only JSON."},
                _image_block(doodle),
            ],
        }])
        parts = []
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        parts.append(block.text)
            elif event.type == "session.status_idle":
                break
        text = "".join(parts)
    # extract the JSON object from the reply
    start, end = text.find("{"), text.rfind("}")
    spec = json.loads(text[start:end + 1])
    validate_spec(spec)  # fail loudly if the interpreter drifted from the contract
    print(f"  Creature: {spec['name']}")
    return spec


def run_coordinator(client, environment_id, coordinator_id, spec: dict) -> str:
    print(f"\nStarting coordinator session...")
    session = client.beta.sessions.create(agent=coordinator_id, environment_id=environment_id,
                                          title=f"Field guide — {spec['name']}")
    Path(".last_session_id").write_text(session.id)
    user_message = (
        "A creature has been interpreted. Here is the Creature Spec (JSON). Run the "
        "field-guide desk: delegate to all four specialists in parallel, then assemble "
        "field-guide.html with your fieldguide-html skill. The doodle is at doodle.png "
        "in your files.\n\n```json\n" + json.dumps(spec, indent=2) + "\n```"
    )
    print("\n=== EVENT STREAM (this is the demo) ===\n")
    text_parts = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message", "content": [{"type": "text", "text": user_message}],
        }])
        for event in stream:
            t = event.type
            if t == "session.thread_created":
                print(f"  [thread spawned]  {getattr(event, 'agent_name', '?')}", flush=True)
            elif t == "agent.thread_message_received":
                print(f"  [reply <-]        {getattr(event, 'from_agent_name', '?')}", flush=True)
            elif t == "agent.thread_message_sent":
                print(f"  [delegate ->]     {getattr(event, 'to_agent_name', '?')}", flush=True)
            elif t == "agent.tool_use":
                print(f"  [tool: {getattr(event, 'name', '?')}]", flush=True)
            elif t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        text_parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif t == "session.status_idle":
                print("\n\n[swarm finished]")
                break
    return session.id


def main() -> None:
    doodle = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOODLE
    if not doodle.exists():
        raise SystemExit(f"Doodle not found: {doodle}")
    _require(".coordinator_id", ".specialist_ids.json", ".environment_id")

    client = managed_client()
    coordinator_id = Path(".coordinator_id").read_text().strip()
    environment_id = Path(".environment_id").read_text().strip()
    interpreter_id = json.loads(Path(".specialist_ids.json").read_text())["interpreter"]

    OUTPUT_DIR.mkdir(exist_ok=True)
    spec = interpret(client, environment_id, interpreter_id, doodle)
    (OUTPUT_DIR / "creature-spec.json").write_text(json.dumps(spec, indent=2))

    session_id = run_coordinator(client, environment_id, coordinator_id, spec)

    print("\nDownloading deliverables from the session container...")
    files = client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
    count = 0
    for f in files.data:
        out = OUTPUT_DIR / f.filename
        client.beta.files.download(f.id).write_to_file(str(out))
        print(f"  {f.filename} -> {out}")
        count += 1
    if count == 0:
        print("  (no files produced — check the session in the console)")
    print(f"\nOpen {OUTPUT_DIR}/field-guide.html in a browser.")
    print(f"Session: https://platform.claude.com/sessions/{session_id}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import run_creature_swarm"`
Expected: exit 0 (no API call at import).

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/run_creature_swarm.py
git commit -m "feat(creature-swarm): run script (interpret -> coordinate -> assemble)"
```

---

## Task 12: `download_deliverable.py`

**Files:**
- Create: `creature-swarm/download_deliverable.py`

**Interfaces:**
- Consumes: `.last_session_id` or a CLI session-id arg; `lib.client.managed_client`.
- Produces: files in `outputs/`.

- [ ] **Step 1: Implement `download_deliverable.py`**

```python
"""Download every file produced by a swarm session.

Usage:
    python download_deliverable.py                # last run (.last_session_id)
    python download_deliverable.py sesn_01ABC...  # a specific session
"""

import sys
from pathlib import Path

from lib.client import managed_client

OUTPUT_DIR = Path("outputs")


def main() -> None:
    if len(sys.argv) > 1:
        session_id = sys.argv[1].strip()
    else:
        last = Path(".last_session_id")
        if not last.exists():
            raise SystemExit("No session id given and .last_session_id not found.")
        session_id = last.read_text().strip()

    client = managed_client()
    files = client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
    OUTPUT_DIR.mkdir(exist_ok=True)
    count = 0
    for f in files.data:
        out = OUTPUT_DIR / f.filename
        client.beta.files.download(f.id).write_to_file(str(out))
        print(f"  {f.filename} -> {out}")
        count += 1
    print(f"\nDownloaded {count} file(s)." if count else "No files on that session.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify import without a key**

Run: `cd creature-swarm && env -u ANTHROPIC_API_KEY python -c "import download_deliverable"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add creature-swarm/download_deliverable.py
git commit -m "feat(creature-swarm): standalone deliverable downloader"
```

---

## Task 13: Synthetic doodle, README, full-suite + live-run verification

**Files:**
- Create: `creature-swarm/synthetic-data/doodle-example.png`
- Create: `creature-swarm/README.md`
- Modify: `creature-swarm/requirements.txt` (pin confirmed `anthropic` version)

**Interfaces:**
- Consumes: everything above.
- Produces: a runnable, documented workshop folder.

- [ ] **Step 1: Create a sample doodle**

Generate a genuinely bad drawing of a made-up animal (any means: draw one and export PNG, or generate a crude one). Save as `synthetic-data/doodle-example.png`. Keep it small (< 1 MB). Verify: `python -c "from pathlib import Path; assert Path('synthetic-data/doodle-example.png').stat().st_size > 0"`.

- [ ] **Step 2: Run the full local test suite**

Run: `cd creature-swarm && python -m pytest -v`
Expected: all tests from Tasks 1–6 PASS. Fix any failures before proceeding.

- [ ] **Step 3: Write `README.md`**

````markdown
# Creature Swarm

Drop in a bad drawing of a made-up animal; a coordinator fans out to specialist
sub-agents (biologist, habitat, society, 3D modeler) that assemble a self-contained
HTML field guide. Built on Claude Managed Agents (multi-agent) + custom Skills.

## Setup
```bash
cd creature-swarm
pip install -r requirements.txt
cp .env.example .env   # add your workspace ANTHROPIC_API_KEY (managed-agents preview)
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Run order
```bash
python setup_environment.py     # provisions the cloud environment (.environment_id)
python create_specialists.py    # interpreter + 4 specialists (.specialist_ids.json)
python upload_skills.py         # uploads + attaches skills
python create_coordinator.py    # coordinator + fieldguide-html skill (.coordinator_id)
python run_creature_swarm.py [synthetic-data/doodle-example.png]
```
Output: `outputs/field-guide.html` (open in a browser; rotate the 3D creature).

## Demo
- Monitor 1: the coordinator event stream — interpreter first, then four parallel
  specialist threads, then assembly.
- Monitor 2: `outputs/field-guide.html`.

## Local tests (no API)
```bash
python -m pytest -v
```

## Stretch
`skills/walk-cycle-anim/` is a stub with a handoff contract — a separate owner
adds `walk-cycle.mp4`, which fills the `{{video}}` slot (already degrades gracefully).
````

- [ ] **Step 4: Live run (requires managed-agents preview access)**

Run the full order above against `doodle-example.png`. Verify, in order:
1. The interpreter returns a Creature Spec that passes `validate_spec` (the run
   script raises if not).
2. The event stream shows four parallel specialist threads.
3. `outputs/field-guide.html` exists and opens; the 3D model rotates; the three
   writeups describe the same creature.

If step 2 shows the coordinator could NOT get the doodle to the modeler/specialists,
that is expected — specialists work from the Spec text, and only the doodle image is
inlined into the page by the coordinator via its files. If the coordinator cannot
access `doodle.png`, pass the doodle as a base64 image block in the coordinator
message too and have the fieldguide skill read it from there.

- [ ] **Step 5: Pin the confirmed `anthropic` version**

After a successful live run, record the working version: `pip show anthropic | grep Version`, then set that as the floor in `requirements.txt` (e.g. `anthropic>=X.Y.Z`).

- [ ] **Step 6: Commit**

```bash
git add creature-swarm/synthetic-data creature-swarm/README.md creature-swarm/requirements.txt
git commit -m "feat(creature-swarm): sample doodle, README, pinned deps"
```

---

## Self-Review

**Spec coverage:**
- Topology (interpreter → spec → parallel specialists → coordinator assembles): Tasks 6, 8, 10, 11. ✓
- Creature Spec consistency contract: consumed in Tasks 2, 11 (validated). ✓
- `fieldguide-html` slot contract: Tasks 4, 5, 10. ✓
- Procedural 3D: Tasks 3, 5. ✓
- Text specialists (biology/habitat/society): Tasks 5, 6. ✓
- Society skill owner's discretion: noted in Tasks 5, 9. ✓
- Animator stub with handoff contract: Task 5. ✓
- HTML field-guide deliverable, all-inlined, graceful degradation: Task 4. ✓
- Original-repo bug fixes (setup_environment in flow; beta header everywhere; dict/object skills; realistic anthropic pin): Tasks 7, 1, 9, 13. ✓
- Demo + team lanes: README (Task 13); each specialist+skill is an independent lane. ✓

**Placeholder scan:** No TBD/TODO in code steps; the animator SKILL.md is an intentional, contract-complete stub (explicitly out of V1 scope), not a placeholder.

**Type consistency:** `build_creature`/`build_creature_glb`, `render_field_guide`, `validate_spec`/`load_spec`, `managed_client`/`MANAGED_AGENTS_BETA`, `INTERPRETER`/`SPECIALISTS`/`COORDINATOR_SYSTEM`/`MODELS`, `_skill_id_of` — names match across tasks.

**Known risk (documented, not a gap):** image-forwarding to sub-agents in managed-agents is unverified; the plan sidesteps it by running the interpreter as a pre-step and by having specialists work from Spec text, with a documented fallback in Task 13 for getting the doodle to the coordinator's assembly step.
