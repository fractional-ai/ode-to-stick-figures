---
name: habitat-ecology
description: Reference guide for writing the habitat and ecology section of an invented-creature field guide entry, grounded in real animal biology and written for kids. Use whenever assigning range, biome, or ecological niche to a creature described by a Creature Spec, for a children's field guide.
---

# Habitat & Ecology

Treat the Creature Spec as ground truth. `locomotion` and `body_plan`
constrain which biomes are plausible — pick a habitat that fits the anatomy,
don't pick one at random and rationalize backward.

## Ground it in a real animal first

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
| walk | Grassland, forest floor, tundra, most terrestrial biomes | Aquatic, sheer cliffs |
| crawl | Forest floor, undergrowth, cave, burrow, rocky shore | Open water, high canopy |
| swim | Aquatic (fresh or marine), wetland | Any fully terrestrial biome |
| fly | Open sky-reliant biomes: canopy, cliffs, open grassland/desert | Deep cave interior, dense enclosed burrow |
| roll | Open flat terrain: desert, grassland, tundra ice | Dense forest understory, cluttered terrain |
| float | Aquatic (fresh or marine), wetland | Any fully terrestrial biome |
| stationary | Attached/sessile biomes: reef, tide pool, forest floor | Anywhere requiring active relocation to escape a threat — flag it as a vulnerability |

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

```
WHERE IT LIVES
[1-2 kid-friendly sentences naming the invented region and what it looks/feels like there]

ITS NEIGHBORHOOD
[1-2 sentences: biome, weather, and how that fits its locomotion/body_plan]

WHO IT SHARES THE FOOD WEB WITH
[1-2 sentences: what it eats or who eats it]

REAL ANIMALS IT'S LIKE
- [real animal #1] — [the one genuine fact you found, in kid language, tied to locomotion or habitat]
- [real animal #2, if you found one] — [same]
```
