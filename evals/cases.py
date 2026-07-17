"""
Eval cases for the Creature Spec harness.

One Case per child drawing in examples/drawings/. Each pairs an input drawing
with a hand-authored fixture spec and a few visual features the LLM judge can
look for. Paths are relative to the repo root (the runner runs from there).
"""

from __future__ import annotations

from contract import Case

CASES: list[Case] = [
    Case(
        id="bee",
        drawing_path="examples/drawings/bee.webp",
        fixture_path="evals/fixtures/bee.json",
        expected_features=["wings", "stripes", "antennae", "smiling face"],
        notes="A big cheerful bumblebee with a yellow-and-black striped oval body, blue wings, and a grinning face, amid flowers and a tree.",
    ),
    Case(
        id="bird",
        drawing_path="examples/drawings/bird.jpg",
        fixture_path="evals/fixtures/bird.json",
        expected_features=["beak", "wings", "webbed feet", "round head"],
        notes="A teal marker bird with a round head, oversized beak, two outstretched feathered wings, and two large fan-shaped webbed feet.",
    ),
    Case(
        id="pencil-creature",
        drawing_path="examples/drawings/pencil-creature.webp",
        fixture_path="evals/fixtures/pencil-creature.json",
        expected_features=["curled limbs", "segmented legs", "eye-spots", "coiled tail"],
        notes="A grey pencil mantis/scorpion-like bug with spiraling curled forelimbs, pink eye-spots, segmented bristly legs, and a coiled tail.",
    ),
    Case(
        id="pig-face",
        drawing_path="examples/drawings/pig-face.webp",
        fixture_path="evals/fixtures/pig-face.json",
        expected_features=["ears", "snout", "smile", "whiskers"],
        notes="A crayon pig face with two rounded ears, big pink eyes, a two-nostril snout, a smiling mouth, and whiskers, framed by green grass.",
    ),
    Case(
        id="shark-dog",
        drawing_path="examples/drawings/shark-dog.webp",
        fixture_path="evals/fixtures/shark-dog.json",
        expected_features=["sharp teeth", "dorsal fin", "tail fin", "four legs"],
        notes="A blue crayon shark-dog hybrid: a shark head with jagged teeth and fins, standing on four dog legs with clawed paws.",
    ),
    Case(
        id="snowmen-scene",
        drawing_path="examples/drawings/snowmen-scene.jpg",
        fixture_path="evals/fixtures/snowmen-scene.json",
        expected_features=["stacked spheres", "top hat", "stick arms", "wintry scene"],
        notes="A painted winter scene with two top-hatted snowmen made of stacked spheres, plus a sun, magenta snow clouds, a blue heart, and blue snow drifts.",
    ),
]
