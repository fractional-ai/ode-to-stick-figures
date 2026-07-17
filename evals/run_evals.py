"""
Creature Spec eval runner.

Loops over the eval cases, obtains a creature spec for each (from a canned
fixture, or from the live Field Interpreter agent once it exists), runs every
deterministic check plus (optionally) the LLM judge, and prints a pass/fail
table. Exits nonzero if any deterministic check fails, so it can gate CI.

Usage:
    python evals/run_evals.py                    # fixtures, deterministic only
    python evals/run_evals.py --llm              # fixtures + LLM judge
    python evals/run_evals.py --target live      # call the real interpreter (stub)
    python evals/run_evals.py --case bee         # run a single case

Run from the repo root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python evals/run_evals.py` from repo root.
sys.path.insert(0, str(Path(__file__).parent))

from cases import CASES  # noqa: E402
from checks import DETERMINISTIC_CHECKS, llm_judge_check  # noqa: E402
from contract import Case, CheckResult  # noqa: E402


def get_spec(case: Case, target: str) -> dict:
    """Return the creature spec for a case from the chosen target.

    'fixture' loads the hand-authored JSON committed alongside the harness, so
    evals run green before any agent exists. 'live' calls the real Field
    Interpreter — stubbed until that agent lands.
    """
    if target == "fixture":
        return json.loads(Path(case.fixture_path).read_text())
    if target == "live":
        return run_interpreter_live(case)
    raise SystemExit(f"Unknown target: {target!r} (use 'fixture' or 'live')")


def run_interpreter_live(case: Case) -> dict:
    """STUB: call the Field Interpreter agent on case.drawing_path -> spec dict.

    Wire this to the managed-agents Interpreter once it exists (mirror the
    session/stream pattern in run_deal_desk.py, send the drawing as an image
    content block, parse the creature-spec.json it returns). Until then, --target
    live is intentionally unsupported.
    """
    raise NotImplementedError(
        "Live target not wired yet: the Field Interpreter agent doesn't exist. "
        "Use --target fixture. See run_deal_desk.py for the session pattern."
    )


def run_case(case: Case, target: str, use_llm: bool) -> list[CheckResult]:
    try:
        spec = get_spec(case, target)
    except Exception as exc:  # noqa: BLE001 - surface any target failure as one FAIL
        return [CheckResult(name="get-spec", passed=False, detail=f"{type(exc).__name__}: {exc}")]

    results = [check(spec, case) for check in DETERMINISTIC_CHECKS]
    if use_llm:
        results.append(llm_judge_check(spec, case))
    return results


def print_report(all_results: dict[str, list[CheckResult]]) -> bool:
    """Print a per-case table. Return True if every deterministic check passed."""
    all_passed = True
    for case_id, results in all_results.items():
        n_pass = sum(r.passed for r in results)
        print(f"\n=== {case_id}  ({n_pass}/{len(results)} passed) ===")
        for r in results:
            line = f"  [{r.symbol}] {r.name}"
            if not r.passed:
                all_passed = False
                line += f"  — {r.detail}"
            print(line)

    total = sum(len(r) for r in all_results.values())
    passed = sum(sum(x.passed for x in r) for r in all_results.values())
    print(f"\n{'-' * 48}")
    print(f"TOTAL: {passed}/{total} checks passed across {len(all_results)} case(s)")
    print("RESULT:", "GREEN ✅" if all_passed else "RED ❌")
    return all_passed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Creature Spec evals.")
    parser.add_argument("--target", default="fixture", choices=["fixture", "live"])
    parser.add_argument("--llm", action="store_true", help="also run the LLM judge")
    parser.add_argument("--case", help="run only this case id (e.g. 'bee')")
    args = parser.parse_args()

    cases = CASES
    if args.case:
        cases = [c for c in CASES if c.id == args.case]
        if not cases:
            raise SystemExit(f"No case with id {args.case!r}. Known: {[c.id for c in CASES]}")

    all_results = {c.id: run_case(c, args.target, args.llm) for c in cases}
    ok = print_report(all_results)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
