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
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
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
    # geom_name keys scene.geometry (node_name only names the transform-graph node),
    # so set both to keep part names queryable off scene.geometry.
    scene.add_geometry(body, node_name="body", geom_name="body")

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
            name = f"{ptype}_{i}_{j}"
            scene.add_geometry(m, node_name=name, geom_name=name)
    return scene


def build_creature_glb(spec: dict, out_path: str) -> str:
    scene = build_creature(spec)
    scene.export(out_path)  # extension (.glb) selects the exporter
    return out_path
