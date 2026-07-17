---
name: habitat-ecology
description: Reference guide for writing the habitat and ecology section of an invented-creature field guide entry. Use whenever assigning range, biome, climate, or ecological niche to a creature described by a Creature Spec. Trigger on any request to place an invented animal in an environment or describe its role in a food web.
---

# Habitat & Ecology

Treat the Creature Spec as ground truth. `locomotion` and `body_plan`
constrain which biomes are plausible — pick a habitat that fits the anatomy,
don't pick one at random and rationalize backward.

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
it — note the tension in one sentence and commit to a resolution (amphibious
lifestyle, seasonal migration) rather than ignoring it.

## How to format your output

```
RANGE
[invented region]

BIOME & CLIMATE
[biome] · [temperature/moisture band] · [one sentence tying it to locomotion/body_plan]

ECOLOGICAL NICHE
[role in food web, 2-3 sentences]
```
