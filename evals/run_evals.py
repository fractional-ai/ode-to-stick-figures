"""
Creature Spec eval runner.

Loops over the eval cases, obtains a creature spec for each (from a canned
fixture, or from the live Field Interpreter agent), runs every deterministic
check plus (optionally) the LLM judge, and prints a pass/fail table. Exits
nonzero if any deterministic check fails, so it can gate CI.

Usage:
    uv run evals/run_evals.py                    # fixtures, deterministic only
    uv run evals/run_evals.py --llm              # fixtures + LLM judge
    uv run evals/run_evals.py --target live      # call the real interpreter
    uv run evals/run_evals.py --case bee         # run a single case

Run from the repo root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `uv run evals/run_evals.py` from repo root.
sys.path.insert(0, str(Path(__file__).parent))

from cases import CASES
from checks import DETERMINISTIC_CHECKS, llm_judge_check
from contract import Case, CheckResult


def get_spec(case: Case, target: str) -> dict:
    """Return the creature spec for a case from the chosen target.

    'fixture' loads the hand-authored JSON committed alongside the harness, so
    evals run green before any agent exists. 'live' calls the real Field
    Interpreter.
    """
    if target == "fixture":
        return json.loads(Path(case.fixture_path).read_text())
    if target == "live":
        return run_interpreter_live(case)
    raise SystemExit(f"Unknown target: {target!r} (use 'fixture' or 'live')")


_SPECIALIST_IDS_PATH = Path(".specialist_ids.json")
_ENVIRONMENT_ID_PATH = Path(".environment_id")
_MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


def _load_doodle_as_image_block(path: Path) -> dict:
    import base64
    import mimetypes

    media_type, _ = mimetypes.guess_type(str(path))
    if media_type is None:
        raise SystemExit(f"Could not determine media type for {path}")
    data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def _parse_spec_text(text: str) -> dict:
    """Parse the Interpreter's reply as JSON, tolerating an accidental ```json fence."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def run_interpreter_live(case: Case) -> dict:
    """Call the real Field Interpreter agent on case.drawing_path -> spec dict.

    Requires ANTHROPIC_API_KEY, .environment_id (written by setup_environment.py),
    and the "interpreter" id in .specialist_ids.json (written by
    create_specialists.py — see evals/README.md). Sends the drawing as an image
    content block in a fresh session, streams the reply, and parses the
    Interpreter's JSON output as the creature spec.
    """
    import os

    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY before running --target live.")
    if not _ENVIRONMENT_ID_PATH.exists() or not _SPECIALIST_IDS_PATH.exists():
        raise SystemExit(
            f"Missing {_ENVIRONMENT_ID_PATH} or {_SPECIALIST_IDS_PATH}. Run "
            "setup_environment.py and create_specialists.py first "
            "(see evals/README.md)."
        )

    environment_id = _ENVIRONMENT_ID_PATH.read_text().strip()
    specialist_ids = json.loads(_SPECIALIST_IDS_PATH.read_text())
    if "interpreter" not in specialist_ids:
        raise SystemExit(
            f'{_SPECIALIST_IDS_PATH} has no "interpreter" key. Re-run create_specialists.py.'
        )
    interpreter_id = specialist_ids["interpreter"]

    client = Anthropic(default_headers={"anthropic-beta": _MANAGED_AGENTS_BETA})
    image_block = _load_doodle_as_image_block(Path(case.drawing_path))

    session = client.beta.sessions.create(
        agent=interpreter_id,
        environment_id=environment_id,
        title=f"Eval — {case.id}",
    )

    final_text_parts: list[str] = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Here is the child's drawing. Emit the Creature "
                                "Spec JSON now, per your system instructions."
                            ),
                        },
                        image_block,
                    ],
                }
            ],
        )
        for event in stream:
            t = event.type
            if t == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        final_text_parts.append(block.text)
            elif t == "session.status_idle":
                break

    return _parse_spec_text("".join(final_text_parts))


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
