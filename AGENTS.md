# Working on Ode to Stick Figures

A child draws an animal that doesn't exist. The pipeline animates it — from the
drawing's own pixels, hinged and moving — and writes it up like an encyclopedia entry.

This file is for agents working on the codebase. The prompts that drive the creature
pipeline live in `agents/definitions.py` and the `skills/` directories; that's a
separate audience from you.

## What kind of project this is

Whimsical, exploratory, creative. Its whole job is to surprise and delight someone.
That has direct consequences for how you should build here, because it inverts a
couple of defaults:

- **The obvious implementation of something is usually the dullest.** When you have a
  choice between the predictable option and a sillier one that still works, take the
  sillier one. "Defensible" is not the bar; "someone smiles at this" is.
- **Boring output is a bug.** A creature that comes out generic, hedged, or lifeless
  is a failure even when every test passes. If you find yourself writing a fallback
  that produces something drab, the fallback is wrong.
- **This does not license sloppiness.** Whimsical output, rigorous machinery. The
  refusal path, the tests, the honesty rules below are not the fun part and they
  still hold.

## Fidelity and delight, both

Two things are true at once and neither outranks the other:

**Use what the child drew.** Every part of a Creature Spec traces to something visible
in the image. A shark-dog is a shark head on a dog body, not an "unusual quadruped."
If legs are drawn, the creature has those legs and walks on them — never overlook what
is on the paper. The child has to recognise their own animal.

**Then be inventive in the gaps.** Where the drawing leaves something open, pick the
answer with the most character rather than the most cautious one. Hedging is the
failure mode: "presumed stationary", "no visible means of locomotion", "none apparent"
are non-answers. A flat limbless cracker-creature isn't motionless — it rocks itself
forward in lurches. Commit to something specific and strange.

The dull-but-defensible reading is the one to avoid. It is also the one a
correctness-focused agent reaches for by default, which is why this is written down.

## Voice

Everything user-facing reads like an encyclopedia written for children: warm, curious,
plainly delighted by the creature, explaining its own hard words. A reference book in
form, not in temperature. Not clinical, not dry, and never talking down.

`skills/creature-biology/SKILL.md` and `skills/habitat-ecology/SKILL.md` have the
detail (short sentences, compare sizes to a school bus or a dinner plate, skip
taxonomy). If you touch a prompt's register, check it against those — they have been
out of step with the prompts before.

## Honesty rules that don't bend

These exist because breaking them produces confident nonsense, which is worse than
producing nothing:

- **A refusal is a real answer and must survive.** `snowmen-scene` is a painting with
  no animal in it, and the gallery says so rather than animating paper slabs sliding
  sideways. Whimsy is not a licence to fabricate an animal where there isn't one, and
  "we'd rather be delightful" must never become the refusal path's escape hatch.
  Enforce refusals where the work happens, not where it's advertised — a direct URL
  once walked straight past the check and billed a full swarm to invent a creature
  from a snowman painting.
- **Never claim progress or state you don't have.** The upload build reports nothing
  until it finishes, so the UI shows an elapsed clock and not a step-by-step ticker.
  Inventing a plausible progress indicator is the same class of error as inventing a
  plausible creature.
- **Say what you didn't do.** If something is untested, unverified, or skipped, say so
  plainly. See below on skips.

## Working here

- **`uv` for everything.** `uv run pytest`, `uv run ui/serve.py`, `uv run
  evals/run_evals.py`. Never a bare `python`.
- **`uv run lefthook install`** once per clone or the pre-commit hooks silently do
  nothing.
- **The test suite is offline and must stay that way.** No API key, no model calls —
  `tests/test_serve.py`'s docstring says so and it's load-bearing. If a test starts
  depending on `ANTHROPIC_API_KEY` being present, pin the flag instead of inheriting
  ambient environment.
- **Never assert on prompt text, and never write a test that restates the code.** A
  substring check on a prompt passes whether or not the prompt works, and fails on a
  reword that changed nothing — it tests the file, not the system. Prompt quality is an
  **eval** (`evals/`), not a unit test. Same for "constant is a non-empty string" or
  "this dict has the keys it visibly has": if a test can only fail when someone edits
  the very line it mirrors, delete it. Test an output, or a contract that spans two
  places and can actually drift.
- **A skipped check must not report as a pass.** Several eval checks degrade to
  `passed=True` when they can't run. Degrading is fine; looking identical to a real
  pass is not.
- **Prewarm before deploying.** The bundled creatures ship as committed artifacts and
  the deployed app never rebuilds them.

## Debugging a deployed problem

Logfire traces everything: request spans (FastAPI), outbound HTTP (both Anthropic and the
hand-rolled Blob calls), Anthropic token usage, plus explicit spans on the expensive
upload path — the alpha key with the image dimensions on it, each swarm phase, and each
text lane separately. `lib/telemetry.py` installs it.

Two things to know before touching it:

- **It is a no-op without `LOGFIRE_TOKEN`.** Spans are created and discarded, so local
  runs and the offline suite behave identically with and without it. `ODE_TELEMETRY=off`
  skips instrumentation outright, which is what the test suite sets — otherwise a
  developer with a token exported would ship test traces to the real project.
- **`OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` is load-bearing, not tidiness.**
  `instrument_anthropic()` records request bodies, and every vision call here carries a
  base64 PNG of a child's drawing. Unlimited, that is multi-megabyte spans per upload and
  someone's artwork sent to a third party. Don't raise it without reading the test.

## The bits that will surprise you

- **`locomotion` is a closed enum because it's a dispatch key** into animation models
  in `skills/walk-cycle-anim/template.html`. Free text silently falls through to an
  ordinary walk. If you add a value, implement the model or map it.
- **Uploaded field guides are served sandboxed** in an iframe with `allow-scripts` and
  deliberately *without* `allow-same-origin`. They're model-written HTML from a
  user-supplied drawing. Don't "fix" that by serving them first-party.
- **`cached()` memoises per model call, not per finished page**, deliberately: assembly
  is the fragile part and the API calls are the expensive part.
- **Artifacts in `ui/prebuilt/` are committed and read-only at runtime.** Vercel's
  filesystem is read-only outside `/tmp`.
