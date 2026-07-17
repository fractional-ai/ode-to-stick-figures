---
name: creature-biology
description: Reference guide for writing the biology section of an invented-creature field guide entry. Use whenever assigning taxonomy, anatomy, diet, or adaptations to a creature described by a Creature Spec. Trigger on any request to classify, describe anatomy, or infer diet/adaptations for an invented animal.
---

# Creature Biology

Treat the Creature Spec as ground truth. Never assert anatomy, diet, or an
adaptation that isn't implied by `body_plan`, `parts`, or
`distinctive_features` — a field guide doesn't speculate past its specimen.

## Taxonomy conventions

Invent a binomial: genus from a Latin/Greek root describing `core_shape` or
the dominant `parts` entry, species from `distinctive_features` or `vibe`.

| `core_shape` | Suggested clade framing |
| --- | --- |
| sphere / ovoid | Invertebrate-leaning order (e.g. "-formes" grouped with molluscs/arthropods) |
| slab | Flattened bottom-dweller order (ray/flounder-adjacent framing) |
| cylinder | Elongate order (worm/eel-adjacent framing) |
| blob | Undifferentiated — commit to a clade anyway; don't hedge with "unclassified" |

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

## How to format your output

```
TAXONOMY
[invented order/family] · [Binomial name]

ANATOMY
[2-4 sentences grounded in body_plan/parts]

DIET
[1-2 sentences, cite the anatomical signal you used]

ADAPTATIONS
- [distinctive_feature] — [one-line survival function]
```
