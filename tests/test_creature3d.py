from pathlib import Path

import trimesh

from tests.conftest import load_module_from_path

BUILD = Path(__file__).resolve().parents[1] / "skills" / "procedural-creature-3d" / "build.py"
build = load_module_from_path("build", BUILD)

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
