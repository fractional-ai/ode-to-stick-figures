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

```
WHAT IT LOOKS LIKE
[2-3 kid-friendly sentences on body shape and size, using a concrete comparison]

WHAT IT EATS
[1-2 sentences, plain language, cite the anatomical signal you used]

REAL ANIMALS IT'S LIKE
- [real animal #1] — [the one genuine fact you found, in kid language, tied to a spec trait]
- [real animal #2, if you found one] — [same]

ITS COOLEST TRICK
[1-2 sentences on the distinctive_feature-based adaptation, explained simply]
```
