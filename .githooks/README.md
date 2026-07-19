# Git hooks

Shared hooks for this repo. They live here (not in `.git/hooks/`) so they can
be version-controlled and shared across the team.

## One-time setup (each clone)

```bash
git config core.hooksPath .githooks
```

That's it. After this, the hooks below run automatically.

## `pre-commit` — keep the task checklist in sync

On every commit, regenerates `TASKS.md` from the working tree and
stages it into the same commit. A task is checked off when all of its declared
output files exist. The task→file mapping is defined in `update-tasks.py`; task
detail lives in `docs/superpowers/plans/2026-07-17-creature-swarm.md`.

- Don't hand-edit checkboxes in `TASKS.md` — they're regenerated each commit.
- Run it by hand any time with `python3 .githooks/update-tasks.py`.
- The hook never blocks a commit; if the updater can't run it's skipped.
- "Done" here means *files present*, a cheap proxy. The real bar is green
  tests (the plan is TDD) — the checklist tracks landing, not correctness.
