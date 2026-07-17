# Example drawings

Test inputs for the animation specialist. Ordered easy → hard so we can tell
whether a change actually improved anything or just moved the failure around.

| File | What it is | Why it's here |
|---|---|---|
| `shark-dog.webp` | Blue shark/dog hybrid, side view, four legs | The ideal case. Clean silhouette, unambiguous quadruped, legs clearly separated from the body. If this doesn't work, nothing will. |
| `bird.jpg` | Green marker bird, wings out, two big feet | Clear limbs, but bipedal with wings — different skeleton from the quadruped. Tests that we're not hardcoding four legs. |
| `bee.webp` | Giant bee with six tiny legs, in a scene | Body is huge, legs are near-invisible scribbles. Also embedded in a scene (tree, flowers, sun) so it needs isolating from the background. |
| `pig-face.webp` | Pig head only, no body | Should degrade gracefully. There's nothing to walk on. Do we bail, or invent legs? Worth deciding on purpose rather than by accident. |
| `pencil-creature.webp` | Ambiguous grey pencil creature | Faint lines, unclear anatomy, overlapping limbs. This is what a real phone photo of a real drawing looks like on a bad day. |
| `snowmen-scene.jpg` | Painted scene: snowmen, sun, clouds, water | Multiple subjects, none of them animals, thick paint with no line art. The stress case — mostly here to see what failure looks like. |
| `walrus-camel-chimera.jpeg` | Walrus head with antlers, tiger-striped camel body, fox tail | Clear hybrid silhouette with four legs — harder anatomy than shark-dog but still a single subject on plain paper. |
| `trunk-scorpion-chimera.jpeg` | Marker chimera: croc/elephant trunk, dragon wing, scorpion tail | Mixed limb types (spots, webbed foot, wing, stinger). Tests that we don't assume a uniform skeleton. |
| `arborescens-triangulum.jpeg` | Vintage atlas plate of a hairy tentacle creature | Fine stipple, no clear limbs for walking, human face. Graceful-degradation case like pig-face, but full-body surreal. |

Provenance: found images, used as test fixtures only.
