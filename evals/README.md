# Creature Spec Evals

Lightweight harness that checks the **Field Interpreter's `creature-spec.json`** —
the contract every downstream agent (Biologist, Habitat, Society, 3D Modeler)
depends on. If the spec is malformed, the whole swarm diverges, so this is the
seam worth guarding.

Specs are validated against the canonical, frozen schema at
`creature-swarm/contracts/creature-spec.schema.json` (via `jsonschema`), and the
per-field checks read their enums straight from it — so the evals track the real
contract and can't silently drift.

## Run it

```bash
# from the repo root
python3 evals/run_evals.py                 # all cases, deterministic checks only
python3 evals/run_evals.py --llm           # also run the LLM-as-judge check
python3 evals/run_evals.py --case bee       # just one case
python3 evals/run_evals.py --target live    # call the real interpreter (stub for now)
```

Exit code is `0` when every deterministic check passes, `1` otherwise — so it can
gate CI. The `--llm` judge never fails the suite; it skips to PASS if there's no
`ANTHROPIC_API_KEY` or the API errors.

## What's here

| File | What it is |
|---|---|
| `contract.py` | Frozen: Creature Spec schema + `Case`/`CheckResult` dataclasses. Change this first if the spec shape changes. |
| `checks.py` | 7 deterministic checks + the one LLM judge. |
| `cases.py` | One `Case` per example drawing in `examples/drawings/`. |
| `fixtures/*.json` | A hand-authored valid spec per drawing, so evals run green before the live agent exists. |
| `run_evals.py` | The runner. |

## Running against the live agent

`--target live` sends each case's drawing to the real Field Interpreter and checks
the spec it returns. Fixtures tell you the checks work; only this tells you the agent
does. It needs:

- `ANTHROPIC_API_KEY`
- `creature-swarm/.environment_id`, written by `creature-swarm/setup_environment.py`
- `creature-swarm/.interpreter_id`, from a one-off interpreter-only agent create

Both ID files are account-specific and gitignored.

```bash
python evals/run_evals.py --target live
python evals/run_evals.py --target live --case bee    # one drawing
```

Worth knowing what this is for: the fixtures are hand-authored and schema-conformant,
so they pass whether or not the Interpreter obeys its own contract. That is how the
palette-as-object and count-as-prose drift went unnoticed long enough to break the 3D
Modeler. A conformant fixture cannot catch a producer that lies. This target can.

## Adding a case

1. Drop a drawing in `examples/drawings/`.
2. Add a `fixtures/<id>.json` (a valid spec).
3. Add a `Case` to `CASES` in `cases.py`.
