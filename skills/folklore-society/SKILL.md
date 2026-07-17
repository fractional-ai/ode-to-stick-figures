---
name: folklore-society
description: Reference guide for writing the society and folklore section of an invented-creature field guide entry. Use whenever assigning social structure, breeding behavior, or local myth to a creature described by a Creature Spec. Trigger on any request to describe social behavior or invent folklore for an invented animal.
---

# Society & Folklore

Treat the Creature Spec as ground truth. `vibe` and `locomotion` are your
strongest signals here — this section has the most creative latitude of the
three text sections, but every choice still has to trace back to the Spec.

## Social structure by vibe/locomotion signal

| Signal | Suggested social structure |
| --- | --- |
| `vibe` reads solitary/skittish, `locomotion` is slither/scuttle | Solitary, territorial |
| `vibe` reads bonded/gentle | Pair-bonded, often monogamous framing |
| `vibe` reads boisterous/social, many legs or a herd-compatible `core_shape` | Pack or colony |
| No strong signal either way | Default to small family groups — the least committal choice that still reads as a decision |

## Breeding notes

One or two lines, field-guide register — clutch/litter size, seasonal timing,
parental investment (do both parents rear young, or one). Keep it clinical,
not graphic.

## Local folklore

Invent exactly one myth or superstition a real field guide would footnote —
a local name distinct from the taxonomic binomial, a superstition tied to
sighting the creature, or a folk explanation for one of its
`distinctive_features`. This is the one place you may quote an invented
"local saying" verbatim, in quotes.

## Voice

Same dry, textbook-authoritative register as the biology and habitat
sections — the folklore content is invented, but the tone reporting it stays
clinical. Don't let the prose wink at the reader.

## How to format your output

```
SOCIAL STRUCTURE
[1-2 sentences, cite the vibe/locomotion signal used]

BREEDING
[1-2 sentences]

LOCAL LORE
[one invented myth or superstition, may include a quoted "local saying"]
```
