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

## Wiring up the live agent

`--target live` calls `run_interpreter_live()` in `run_evals.py`, which is a stub
today. Once the Field Interpreter agent exists, wire that function to send the
drawing to it and parse the returned spec (see `run_deal_desk.py` for the
managed-agents session/stream pattern). No other file needs to change.

## Adding a case

1. Drop a drawing in `examples/drawings/`.
2. Add a `fixtures/<id>.json` (a valid spec).
3. Add a `Case` to `CASES` in `cases.py`.
