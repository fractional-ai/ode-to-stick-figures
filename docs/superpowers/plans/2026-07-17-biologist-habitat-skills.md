# Biologist & Habitat Kid-Friendly, Real-Animal-Grounded Skills — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the root flat pattern's `creature-biology` and `habitat-ecology`
skills (plus their matching specialist system prompts) so both agents research
real animals before writing, and write for a child audience, instead of the
current deadpan adult-register field-guide prose.

**Architecture:** Content-only changes to two `SKILL.md` files and two system
prompt strings inside `create_specialists.py` (root flat pattern only — the
`creature-swarm/` subfolder pattern is untouched). No new infra: the
`agent_toolset_20260401` toolset already grants web_search/web_fetch, and
`upload_skills.py`'s `SKILL_TO_SPECIALIST` mapping is already wired correctly.
A small standalone test script is added so each specialist agent can be
smoke-tested in its own session, without spinning up the whole coordinator.

**Tech Stack:** Python 3, `anthropic` SDK (managed-agents preview beta header
`managed-agents-2026-04-01`).

**Design doc:** `docs/superpowers/specs/2026-07-17-biologist-habitat-skills-design.md`

---

## Task 1: Rewrite `skills/creature-biology/SKILL.md`

**Files:**
- Modify: `skills/creature-biology/SKILL.md` (full rewrite)

**Step 1: Write the new file**

```markdown
---
name: creature-biology
description: Reference guide for writing the biology section of an invented-creature field guide entry, grounded in real animal biology and written for kids. Use whenever assigning anatomy, diet, life cycle, or physiology to a creature described by a Creature Spec, for a children's field guide.
---

# Creature Biology

Treat the Creature Spec as ground truth. Never assert anatomy, diet, or an
adaptation that isn't implied by `body_plan`, `parts`, or
`distinctive_features` — a field guide doesn't speculate past its specimen.

## Step 1: Find the real animals it's like

Before writing, use your web search/fetch tools to find 1-2 REAL animals
whose real biology plausibly explains a notable trait in the spec. Pick the
trait that's hardest to explain and go look it up — don't skip this because
it "seems obvious." Examples of what to look up:

- Six legs on a big body? Look up how real many-legged animals (insects,
  myriapods) actually distribute weight, and whether that holds up at a
  bigger size.
- A wide flat part near the mouth? Look up real filter feeders (baleen
  whales, flamingos) and how their mouths actually work.
- Bright colors? Look up real examples of warning coloration (poison dart
  frogs) vs. camouflage vs. mate attraction, and pick the one that fits.

Bring back ONE genuine fact per animal you look up. You'll use it to build
the "Real Animals It's Like" section below.

## Anatomy write-up by leg/limb count

| `parts` entry (type: leg) | Framing |
| --- | --- |
| count 0 | Legless — locomotion must come from another part or body undulation |
| count 2 | Bipedal — note center-of-mass implications for `size_est_m` |
| count 4 | Standard quadruped |
| count 6+ | Arthropod-leaning gait; describe in sets (tripod gait), not as a single blob of legs |

Non-leg parts (eyestalks, horns, tails, wings) get one sentence each,
grounded in `placement` and `shape` — don't invent a function the Spec
doesn't support.

## Diet inference rules

| Anatomical signal | Inferred diet |
| --- | --- |
| Grasping/pincer-shaped part present | Omnivore or predator |
| Many legs, no manipulating part | Grazer/browser |
| Wide flat mouth-adjacent feature, no visible teeth-type part | Filter feeder |
| No clear feeding-relevant part in the Spec | Default to generalist omnivore and say so plainly — don't invent a part to justify a diet |

## Adaptation write-up

For each `distinctive_features` entry, give it exactly one plausible survival
function (camouflage, signaling, defense, thermoregulation). Pick the
function that best fits `locomotion` and habitat implications — don't stack
multiple functions onto one feature.

## Writing for kids

Your reader is a kid, so:

- Short sentences. One idea per sentence.
- Compare sizes and shapes to things a kid has actually seen: a school bus,
  a dinner plate, a soccer ball, a garden hose — not "moderately large" or
  "elongated."
- Explain any hard word the moment you use it: "an exoskeleton — a hard
  shell on the OUTSIDE of the body, like a suit of armor — ..."
- Warm and curious tone, not clinical. It's okay to sound delighted by the
  creature.
- Never use a mock-Latin binomial or formal taxonomy — kids don't care about
  genus and species, they care about what the animal does.

## How to format your output

\```
WHAT IT LOOKS LIKE
[2-3 kid-friendly sentences on body shape and size, using a concrete comparison]

WHAT IT EATS
[1-2 sentences, plain language, cite the anatomical signal you used]

REAL ANIMALS IT'S LIKE
- [real animal #1] — [the one genuine fact you found, in kid language, tied to a spec trait]
- [real animal #2, if you found one] — [same]

ITS COOLEST TRICK
[1-2 sentences on the distinctive_feature-based adaptation, explained simply]
\```
```

**Step 2: Verify frontmatter is well-formed**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && head -4 skills/creature-biology/SKILL.md`
Expected:
```
---
name: creature-biology
description: Reference guide for writing the biology section of an invented-creature field guide entry, grounded in real animal biology and written for kids. Use whenever assigning anatomy, diet, life cycle, or physiology to a creature described by a Creature Spec, for a children's field guide.
---
```

**Step 3: Commit**

```bash
git add skills/creature-biology/SKILL.md
git commit -m "feat(creature-biology): ground in real-animal research, write for kids"
```

---

## Task 2: Update the `biologist` system prompt in `create_specialists.py`

**Files:**
- Modify: `create_specialists.py:50-68` (the `biologist` entry in `SPECIALISTS`)

**Step 1: Replace the entry**

Find this block:

```python
    {
        "key": "biologist",
        "name": "Biologist",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Biologist in a Creature Swarm. Your job is to "
            "write the biology section of a field guide entry for an "
            "invented creature.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The creature-biology skill (your authoritative style guide)\n\n"
            "Your output: a markdown section covering:\n"
            "1. Taxonomy (invent a plausible clade + mock-Latin binomial)\n"
            "2. Anatomy (grounded in body_plan/parts)\n"
            "3. Diet\n"
            "4. Adaptations implied by distinctive_features\n\n"
            "Treat the Spec as literal fact. Don't contradict it."
        ),
    },
```

Replace with:

```python
    {
        "key": "biologist",
        "name": "Biologist",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Biologist in a Creature Swarm. Your job is to "
            "write the biology section of a field guide entry for an "
            "invented creature, for an audience of kids.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The creature-biology skill (your authoritative style guide)\n\n"
            "Before writing, use your web search/fetch tools to research 1-2 "
            "REAL animals whose real biology explains a notable trait in the "
            "Spec — bring back one genuine fact per animal.\n\n"
            "Your output: a kid-friendly markdown section covering:\n"
            "1. What it looks like (concrete size/shape comparisons)\n"
            "2. What it eats\n"
            "3. Real animals it's like (the facts you researched)\n"
            "4. Its coolest trick (an adaptation tied to a "
            "distinctive_features entry)\n\n"
            "Treat the Spec as literal fact. Don't contradict it. Short "
            "sentences, explain any hard word the moment you use it — no "
            "taxonomic Latin, no clinical tone."
        ),
    },
```

**Step 2: Verify the file still parses**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && python3 -c "import ast; ast.parse(open('create_specialists.py').read())"`
Expected: no output, exit 0.

**Step 3: Commit**

```bash
git add create_specialists.py
git commit -m "feat(creature-swarm): biologist prompt researches real animals, writes for kids"
```

---

## Task 3: Rewrite `skills/habitat-ecology/SKILL.md`

**Files:**
- Modify: `skills/habitat-ecology/SKILL.md` (full rewrite)

**Step 1: Write the new file**

```markdown
---
name: habitat-ecology
description: Reference guide for writing the habitat and ecology section of an invented-creature field guide entry, grounded in real animal biology and written for kids. Use whenever assigning range, biome, climate, or ecological niche to a creature described by a Creature Spec, for a children's field guide.
---

# Habitat & Ecology

Treat the Creature Spec as ground truth. `locomotion` and `body_plan`
constrain which biomes are plausible — pick a habitat that fits the anatomy,
don't pick one at random and rationalize backward.

## Step 1: Find the real animal it's like

Before writing, use your web search/fetch tools to find 1-2 REAL animals
that actually live the way the spec's `locomotion` implies, and look up one
real fact about where they live or how they survive there. Examples:

- `locomotion: float` → look up a real animal that spends its life floating
  (jellyfish, sea otter) and one real fact about how it survives there.
- `locomotion: slither` → look up a real burrowing or slithering animal
  (snake, caecilian) and one real fact about its hideout.

Bring back ONE genuine fact per animal you look up, for the "Real Animals
It's Like" section below.

## Locomotion → biome compatibility

| `locomotion` | Compatible biomes | Poor fit (flag if forced) |
| --- | --- | --- |
| waddle | Wetland, tundra, coastal | Steep terrain, dense forest understory |
| hop | Grassland, scrub, open desert | Aquatic, dense canopy |
| slither | Forest floor, cave, burrow, wetland | Open exposed terrain (no cover) |
| scuttle | Rocky shore, cave, forest floor | Open water |
| float | Aquatic (fresh or marine), wetland | Any fully terrestrial biome |
| other | Justify explicitly in one sentence — don't leave it unaddressed | — |

## Range

Invent one specific, plausible-sounding region (a fictional mountain range,
archipelago, or basin reads better than a vague continent name). Keep it
internally consistent with the biome chosen above.

## Climate preference

State a temperature band and moisture level. Cross-check against `palette`
if it contains desaturated/pale tones (cold or low-light adaptation) or
saturated/bright tones (warm, high-visibility environment) — mention the
connection if the palette supports it, skip it if it doesn't.

## Ecological niche

| Diet signal (from the Biologist's inference, or infer independently from `parts`) | Role in food web |
| --- | --- |
| Predator anatomy | Mid-to-apex, name one plausible prey type |
| Grazer/browser anatomy | Primary consumer, name one plausible predator |
| Filter feeder | Base-of-chain, largely predator-free or name one specialist predator |
| Generalist omnivore | Flexible niche — say so, don't force a single slot |

## How to flag inconsistencies

If `locomotion` and the most obvious biome choice conflict (e.g. `float`
with a `size_est_m` implying a large land mass), don't silently paper over
it — tell the reader about the puzzle in one plain sentence and commit to a
fun resolution (it swims most of the time and only comes on land to nest,
say) rather than ignoring it.

## Writing for kids

Your reader is a kid, so:

- Short sentences. One idea per sentence.
- Describe the home the way you'd describe it to a friend: "It lives in
  warm, shallow swamps, hiding under lily pads the size of trash can
  lids" — not "prefers humid subtropical wetland environments."
- Explain any hard word the moment you use it.
- Warm, curious tone — you're showing off a cool place, not filing a report.
- Skip taxonomic/scientific register entirely.

## How to format your output

\```
WHERE IT LIVES
[1-2 kid-friendly sentences naming the invented region and what it looks/feels like there]

ITS NEIGHBORHOOD
[1-2 sentences: biome, weather, and how that fits its locomotion/body_plan]

WHO IT SHARES THE FOOD WEB WITH
[1-2 sentences: what it eats or who eats it]

REAL ANIMALS IT'S LIKE
- [real animal #1] — [the one genuine fact you found, in kid language, tied to locomotion or habitat]
- [real animal #2, if you found one] — [same]
\```
```

**Step 2: Verify frontmatter is well-formed**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && head -4 skills/habitat-ecology/SKILL.md`
Expected:
```
---
name: habitat-ecology
description: Reference guide for writing the habitat and ecology section of an invented-creature field guide entry, grounded in real animal biology and written for kids. Use whenever assigning range, biome, climate, or ecological niche to a creature described by a Creature Spec, for a children's field guide.
---
```

**Step 3: Commit**

```bash
git add skills/habitat-ecology/SKILL.md
git commit -m "feat(habitat-ecology): ground in real-animal research, write for kids"
```

---

## Task 4: Update the `habitat` system prompt in `create_specialists.py`

**Files:**
- Modify: `create_specialists.py` (the `habitat` entry in `SPECIALISTS`, now shifted a few lines down from Task 2's edit — locate by the `"key": "habitat"` marker, not a fixed line number)

**Step 1: Replace the entry**

Find this block:

```python
    {
        "key": "habitat",
        "name": "Habitat",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Habitat specialist in a Creature Swarm. Your job "
            "is to write the habitat and ecology section of a field guide "
            "entry for an invented creature.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The habitat-ecology skill (your authoritative style guide)\n\n"
            "Your output: a markdown section covering:\n"
            "1. Range\n"
            "2. Biome and climate preference\n"
            "3. Ecological niche (diet, predators, role in the food web)\n"
            "4. How locomotion and body_plan suit the chosen environment\n\n"
            "Treat the Spec as literal fact. Don't contradict it."
        ),
    },
```

Replace with:

```python
    {
        "key": "habitat",
        "name": "Habitat",
        "model": "claude-sonnet-4-6",
        "system": (
            "You are the Habitat specialist in a Creature Swarm. Your job "
            "is to write the habitat and ecology section of a field guide "
            "entry for an invented creature, for an audience of kids.\n\n"
            "Inputs you'll receive:\n"
            "- The Creature Spec (JSON)\n"
            "- The habitat-ecology skill (your authoritative style guide)\n\n"
            "Before writing, use your web search/fetch tools to research 1-2 "
            "REAL animals that actually live the way this creature's "
            "locomotion implies — bring back one genuine fact per animal.\n\n"
            "Your output: a kid-friendly markdown section covering:\n"
            "1. Where it lives\n"
            "2. Its neighborhood (biome, weather, how locomotion/body_plan "
            "suit the environment)\n"
            "3. Who it shares the food web with\n"
            "4. Real animals it's like (the facts you researched)\n\n"
            "Treat the Spec as literal fact. Don't contradict it. Short "
            "sentences, explain any hard word the moment you use it — no "
            "clinical tone."
        ),
    },
```

**Step 2: Verify the file still parses**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && python3 -c "import ast; ast.parse(open('create_specialists.py').read())"`
Expected: no output, exit 0.

**Step 3: Commit**

```bash
git add create_specialists.py
git commit -m "feat(creature-swarm): habitat prompt researches real animals, writes for kids"
```

---

## Task 5: Static wiring check (no code changes expected)

**Files:**
- Read-only check: `upload_skills.py`

**Step 1: Confirm `SKILL_TO_SPECIALIST` still routes both skills correctly**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && grep -A5 "SKILL_TO_SPECIALIST" upload_skills.py`
Expected: `"creature-biology": "biologist",` and `"habitat-ecology": "habitat",` both present.

If either mapping is missing or wrong, fix `upload_skills.py` and commit — but per the design doc this should already be correct, so this step is a confirmation, not expected to require a change.

---

## Task 6: Standalone specialist test script

**Files:**
- Create: `test_specialist_standalone.py`

**Step 1: Write the script**

```python
"""
Send a fixture Creature Spec to a single specialist agent, bypassing the
coordinator entirely. Lets you smoke-test one specialist's skill + prompt in
isolation, per the Testing section of
docs/superpowers/specs/2026-07-17-biologist-habitat-skills-design.md.

Usage:
    python test_specialist_standalone.py <agent_key> [path/to/spec.json]

<agent_key> is a key from .specialist_ids.json (e.g. "biologist", "habitat").
Defaults to creature-swarm/contracts/creature-spec.example.json for the spec.
"""

import json
import sys
from pathlib import Path

from anthropic import Anthropic

DEFAULT_SPEC_PATH = Path("creature-swarm/contracts/creature-spec.example.json")
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: python {sys.argv[0]} <agent_key> [spec.json]")
    agent_key = sys.argv[1]
    spec_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_SPEC_PATH

    ids_path = Path(".specialist_ids.json")
    if not ids_path.exists():
        raise SystemExit("Run create_specialists.py + upload_skills.py first.")
    specialist_ids = json.loads(ids_path.read_text())
    if agent_key not in specialist_ids:
        raise SystemExit(f"Unknown agent_key {agent_key!r}. Known: {list(specialist_ids)}")
    agent_id = specialist_ids[agent_key]

    env_path = Path(".environment_id")
    if not env_path.exists():
        raise SystemExit("Run setup_environment.py first.")
    environment_id = env_path.read_text().strip()

    spec_text = spec_path.read_text()

    client = Anthropic(default_headers={"anthropic-beta": MANAGED_AGENTS_BETA})
    print(f"Starting standalone session against {agent_key} ({agent_id})...")
    session = client.beta.sessions.create(
        agent=agent_id, environment_id=environment_id, title=f"Standalone test — {agent_key}"
    )

    user_message = (
        "Here is the Creature Spec for a field guide entry. Write your "
        "section.\n\n```json\n" + spec_text + "\n```"
    )

    parts = []
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": user_message}]}],
        )
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if getattr(block, "type", None) == "text":
                        parts.append(block.text)
                        print(block.text, end="", flush=True)
            elif event.type == "session.status_idle":
                print("\n\n[done]")
                break

    out_path = Path(f"outputs/standalone-{agent_key}.md")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text("".join(parts))
    print(f"\nSaved reply to {out_path}")


if __name__ == "__main__":
    main()
```

**Step 2: Verify it imports without an API key**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && python3 -c "import ast; ast.parse(open('test_specialist_standalone.py').read())"`
Expected: no output, exit 0.

**Step 3: Commit**

```bash
git add test_specialist_standalone.py
git commit -m "feat(creature-swarm): standalone single-specialist test harness"
```

---

## Task 7: Live verification (requires managed-agents preview access)

**Files:** none (execution only)

**Step 1: Check for API access**

Run: `echo $ANTHROPIC_API_KEY | cut -c1-7`
If empty, STOP this task — report to the user that live verification is outstanding and why, and skip to Task 8.

**Step 2: Run the pipeline up through skill upload**

```bash
cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills
python3 setup_environment.py
python3 create_specialists.py
python3 upload_skills.py
```
Expected: `.environment_id`, `.specialist_ids.json`, `.skill_ids.json` created; `biologist` and `habitat` both show `attached ✓`.

**Step 3: Smoke-test both agents standalone**

```bash
python3 test_specialist_standalone.py biologist
python3 test_specialist_standalone.py habitat
```
Expected: each prints a markdown reply matching its new output format
(`WHAT IT LOOKS LIKE` / ... / `REAL ANIMALS IT'S LIKE` for biologist;
`WHERE IT LIVES` / ... / `REAL ANIMALS IT'S LIKE` for habitat), citing at
least one real animal by name with a fact that's actually true, in
kid-readable language with no unexplained jargon. Read both replies in full
before declaring success — this is a content-quality check a passing exit
code can't verify by itself.

**Step 4: Report result to the user**

Summarize whether both replies met the design's bar (real-animal grounding +
kid-readable) or what fell short, quoting the specific line that's off if
something needs a follow-up prompt tweak.

---

## Task 8: Wrap-up

**Step 1: Review full diff**

Run: `cd /Users/nicholasbindela/Documents/Fractional/Basecamp/ode-to-stick-figures/.worktrees/biologist-habitat-skills && git log --oneline main..HEAD`
Expected: one commit per task above (5-7 commits depending on whether Task 7 needed a follow-up commit).

**Step 2: Hand off**

Report the worktree path and branch name to the user and ask whether to open
a PR, merge locally, or leave it for further review — per
superpowers:finishing-a-development-branch.
