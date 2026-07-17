#!/usr/bin/env python3
"""Regenerate creature-swarm/TASKS.md from the state of the working tree.

A task is checked off when every one of its declared output files exists.
This is a deterministic proxy for "done" — the real bar is green tests
(the plan is TDD), but file presence is what we can check cheaply on every
commit. Source of truth for task detail:
docs/superpowers/plans/2026-07-17-creature-swarm.md

Run automatically by .githooks/pre-commit; safe to run by hand any time.
"""
from __future__ import annotations

import os
import subprocess
import sys

# (id, title, [output files relative to repo root])
TASKS = [
    ("1", "Scaffold folder, requirements, and shared managed-agents client",
     ["creature-swarm/requirements.txt", "creature-swarm/.env.example",
      "creature-swarm/lib/client.py"]),
    ("2", "Creature Spec loader + validator",
     ["creature-swarm/lib/spec.py", "creature-swarm/tests/test_spec.py"]),
    ("3", "Procedural 3D builder (trimesh -> glb)",
     ["creature-swarm/skills/procedural-creature-3d/build.py",
      "creature-swarm/tests/test_creature3d.py"]),
    ("4", "Field-guide HTML renderer + template",
     ["creature-swarm/skills/fieldguide-html/template.html",
      "creature-swarm/skills/fieldguide-html/render.py",
      "creature-swarm/tests/test_fieldguide.py"]),
    ("5", "Author the specialist skills (SKILL.md files)",
     ["creature-swarm/skills/creature-biology/SKILL.md",
      "creature-swarm/skills/habitat-ecology/SKILL.md",
      "creature-swarm/skills/folklore-society/SKILL.md"]),
    ("6", "Agent definitions (system prompts + roster config)",
     ["creature-swarm/agents/definitions.py"]),
    ("7", "setup_environment.py",
     ["creature-swarm/setup_environment.py"]),
    ("8", "create_specialists.py",
     ["creature-swarm/create_specialists.py"]),
    ("9", "upload_skills.py (with the object-vs-dict fix)",
     ["creature-swarm/upload_skills.py"]),
    ("10", "create_coordinator.py",
     ["creature-swarm/create_coordinator.py"]),
    ("11", "run_creature_swarm.py",
     ["creature-swarm/run_creature_swarm.py"]),
    ("12", "download_deliverable.py",
     ["creature-swarm/download_deliverable.py"]),
    ("13", "Synthetic doodle, README, full-suite + live-run verification",
     ["creature-swarm/synthetic-data/doodle-example.png",
      "creature-swarm/README.md"]),
]

# Already merged via a separate PR — a read-only input, shown for context.
PREREQ = [
    ("Creature Spec contract",
     ["creature-swarm/contracts/creature-spec.schema.json",
      "creature-swarm/contracts/creature-spec.example.json"]),
]

# Additional workstreams surfaced in the kickoff notes
# (https://notes.granola.ai/t/d4a99333-80ce-4316-841c-ead6f4fca06e-009c2hma)
# that the 13-task build plan does not track explicitly.
ADDITIONAL = [
    ("A1", "Image intake & alpha-key normalization (hand-drawn art pipeline)",
     ["creature-swarm/skills/walk-cycle-anim/build_walk_cycle.py"]),
    ("A2", "Image-to-structure parsing — infer body/limbs into rigs",
     ["creature-swarm/skills/walk-cycle-anim/rigs"]),
    ("A3", "Eval suite — deterministic field-guide checks + LLM-as-judge policy",
     ["creature-swarm/evals/run_evals.py"]),
]

# Stretch goal — ships as a stub in V1, tracked but not counted in the 13.
STRETCH = [
    ("S", "Walk-cycle animator (stub -> full)",
     ["creature-swarm/skills/walk-cycle-anim/SKILL.md"]),
]

OUTPUT = "creature-swarm/TASKS.md"


def repo_root() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()


def candidates(f: str) -> list[str]:
    """Where a declared output file might actually live.

    The plan puts everything under creature-swarm/, but some lanes landed
    the same files at the repo root. Check both so the checklist reflects
    reality regardless of which layout a teammate used.
    """
    cands = [f]
    prefix = "creature-swarm/"
    if f.startswith(prefix):
        cands.append(f[len(prefix):])
    return cands


def resolve(root: str, f: str) -> str | None:
    for c in candidates(f):
        if os.path.exists(os.path.join(root, c)):
            return c
    return None


def done(root: str, files: list[str]) -> bool:
    return all(resolve(root, f) is not None for f in files)


def authors(root: str, files: list[str]) -> list[str]:
    """Distinct commit authors across a task's existing output files."""
    names: set[str] = set()
    for f in files:
        r = resolve(root, f)
        if r is None:
            continue
        try:
            out = subprocess.check_output(
                ["git", "log", "--format=%an", "--", r],
                cwd=root, text=True, stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue
        names.update(n.strip() for n in out.splitlines() if n.strip())
    return sorted(names)


def box(is_done: bool) -> str:
    return "[x]" if is_done else "[ ]"


def by_line(root: str, files: list[str]) -> str:
    names = authors(root, files)
    return f" — _{', '.join(names)}_" if names else ""


def task_block(root: str, label: str, title: str, files: list[str]) -> list[str]:
    filelist = ", ".join(f"`{f}`" for f in files)
    head = f"- {box(done(root, files))} {label}{title}{by_line(root, files)}"
    return [head, f"  <br/>outputs: {filelist}"]


def render(root: str) -> str:
    v1_done = sum(1 for _, _, files in TASKS if done(root, files))
    add_done = sum(1 for _, _, files in ADDITIONAL if done(root, files))
    lines = [
        "# Creature Swarm — Task Checklist",
        "",
        "> Auto-generated by `.githooks/pre-commit` on every commit. A task is",
        "> checked off when all of its output files exist in the repo, and the",
        "> author(s) shown are the committers of those files. **Do not hand-edit**",
        "> — checkboxes and names are regenerated and re-staged each commit. Full",
        "> task detail: `docs/superpowers/plans/2026-07-17-creature-swarm.md`.",
        "",
        f"**V1 plan: {v1_done}/{len(TASKS)} complete.** "
        f"**Kickoff-notes workstreams: {add_done}/{len(ADDITIONAL)} complete.**",
        "",
        "## Prerequisite (merged separately)",
        "",
    ]
    for title, files in PREREQ:
        lines.append(f"- {box(done(root, files))} {title} "
                     f"(`{files[0]}`){by_line(root, files)}")
    lines += ["", "## V1 tasks (build plan)", ""]
    for tid, title, files in TASKS:
        lines += task_block(root, f"**Task {tid}** — ", title, files)
    lines += ["", "## Additional workstreams (from kickoff notes)", ""]
    for aid, title, files in ADDITIONAL:
        lines += task_block(root, f"**{aid}** — ", title, files)
    lines += ["", "## Stretch", ""]
    for _tid, title, files in STRETCH:
        lines += task_block(root, "", title, files)
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = repo_root()
    content = render(root)
    path = os.path.join(root, OUTPUT)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
