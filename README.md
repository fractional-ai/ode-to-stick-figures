# Ode to Stick Figures

Hand a child's drawing of a made-up animal to a swarm of agents and get back a field
guide entry written like an encyclopedia for children — the biology, the habitat, the
folklore — and the creature itself up and moving.

The animation is the drawing's own pixels, not a reconstruction. We cut the paper
away, hinge the parts the child drew, and set them moving. It stays recognisably
theirs. Only three of the thirteen actually walk: the rest buzz, undulate, hop, or
rock themselves forward in lurches, because a flat cracker-shaped creature deserves
better than standing still.

## Run the gallery

```bash
cp .env.example .env      # add your ANTHROPIC_API_KEY
uv run lefthook install   # once per clone, wires the pre-commit/pre-push hooks
uv run ui/serve.py        # http://127.0.0.1:8000
```

Dependencies and the Python version live in `pyproject.toml` and `uv.lock`, and
[uv](https://docs.astral.sh/uv/) fetches both on first run. Nothing to install.

The `lefthook install` step matters: an uninstalled git hook is invisible and does
nothing, which is exactly what happened to this repo's original `.githooks/` setup
before it was retired.

The example drawings ship with their animations and field guides already built and
checked in, so a fresh clone is all cache hits and costs no API calls. Drop a new
drawing on the gallery to run it through the swarm live.

One drawing has no animation on purpose. `snowmen-scene` is a painted scene with no
animal in it, and the gallery says so rather than animating paper slabs sliding
sideways. An honest refusal is a feature; plausible garbage is the worst thing we
could show.

## Deploying to Vercel

The gallery is a single FastAPI app (`ui/serve.py`); `api/index.py` just re-exports
it from where Vercel's Python runtime expects to find one. Uploading a drawing is
gated to a real Google Workspace account; browsing — including anything an
already-uploaded creature produced — stays public regardless.

Live at <https://ode-to-stick-figures.vercel.app>, on the `fractional-ai` team.

What deploying needs, beyond `git push`:

- **A plan whose function duration covers a real upload build.** Rig authoring plus
  the full swarm measured at ~51s for one drawing with no retries, and `vercel.json`
  asks for `maxDuration: 180`. Pro covers this comfortably. (An earlier version of this
  section claimed Hobby's ceiling was the blocker; the default is 300s across plans
  now, so duration wasn't the reason to be on Pro.)
- **A Google Cloud OAuth 2.0 Client ID** (Web application), with
  `https://<your-domain>/auth/callback` as an authorized redirect URI — exactly, or
  Google fails the sign-in with `redirect_uri_mismatch`. Set `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET`, and `ALLOWED_EMAIL_DOMAINS` (see `.env.example`). Setting
  neither client var leaves uploads open with no login, which is deliberate for local
  dev; setting only one disables uploads outright rather than quietly opening them —
  see `ui/auth.py`.
- **A `SESSION_SECRET`** — any long random string, signs the session cookie.
  Required once `GOOGLE_CLIENT_ID` is set; `ui/auth.py` refuses to start without it.
- **A Vercel Blob store**, linked to the project. Auto-injects
  `BLOB_READ_WRITE_TOKEN`, which is what switches uploaded creatures from local disk
  (`ui/storage.py`'s dev backend) to Blob (its production one) — nothing else about
  the app changes. `BLOB_STORE_ID` is *not* injected and isn't needed: the token
  embeds the store id and `BlobStorage` derives it.
- **"Access to System Environment Variables"** enabled in Project Settings, so
  `VERCEL=1` is actually populated at runtime — this is what tells the bundled 13
  creatures never to attempt a live rebuild against Vercel's read-only filesystem
  (see `ON_VERCEL` in `ui/serve.py`).
- **`ui/prewarm.py` run before every deploy.** The bundled 13 creatures are shipped as
  committed, read-only files; the deployed app never rebuilds them. Skipping this
  before a deploy means a real gap, surfaced honestly as "needs a prewarm and a
  redeploy" rather than a crash — not a cache the live app can fill on its own.
  Issue #61 tracks moving these out of git so they stop riding along with a deploy.

## How it works

The **Field Interpreter** looks at the drawing once and emits a **Creature Spec**.
That Spec is the consistency seam: every other lane keys off it, so they all
describe the same animal rather than four different ones.

```
                        drawing
                           │
                  Field Interpreter (vision)
                           │
                    Creature Spec  ──────── contracts/creature-spec.schema.json
                           │
        ┌──────────┬───────┴───────┬──────────┐
   Biologist    Habitat        Society     Animator
        └──────────┴───────┬───────┴──────────┘
                           │
                     field guide page
```

The Spec is a frozen contract with real enums, validated in
`contracts/creature-spec.schema.json`.

The roster, and what each lane reads and writes:

| Agent | Reads | Writes |
| --- | --- | --- |
| **Field Interpreter** (vision) | the drawing | the Creature Spec |
| **Creature Biologist** | Spec | the biology section |
| **Habitat Ecologist** | Spec | the habitat section |
| **Folklore & Society Specialist** | Spec | the society section |
| **Animator** (vision) | the drawing, plus the Spec's name/vibe/palette | the walk cycle |
| **3D Modeler** | Spec | a procedural `.glb` |
| **Coordinator** | all of the above | the field guide page |

Prompts and model tiers for every one of them are in `agents/definitions.py`, which
is pure data — network-free and testable. The Animator gets the drawing itself, not
just the Spec: image-space geometry is the one thing the Spec deliberately doesn't
carry, so the frozen seam stays frozen. The 3D model is the weakest lane and the
template degrades without it.

## Layout

```
agents/definitions.py    the roster and every prompt, network-free and testable
contracts/               the Creature Spec schema + example (the frozen contract)
lib/                     shared Anthropic client, spec validation
skills/
├── walk-cycle-anim/     the 2.5D cutout animator: alpha-key, rigs, renderer
├── fieldguide-html/     assembles the page
├── creature-biology/    ─┐
├── habitat-ecology/      ├ the text lanes
├── folklore-society/    ─┘
└── procedural-creature-3d/build.py   called directly, not a hosted skill (no SKILL.md)
ui/                      the gallery: serve.py, pipeline.py, prewarm.py
evals/                   Creature Spec eval harness
examples/field-guides/   a full field guide assembled outside the gallery, for reference
examples/drawings/       the drawings, ordered easy to hard
tests/
setup_environment.py, create_specialists.py, upload_skills.py, create_coordinator.py
                         provision the managed-agents lane (see below); unused by the gallery
```

## The managed-agents lane

The four scripts at the root provision the swarm as hosted agents on the
managed-agents preview, in this order:

```bash
uv run setup_environment.py    # writes .environment_id
uv run create_specialists.py   # writes .specialist_ids.json
uv run upload_skills.py        # attaches the skills, writes .skill_ids.json
uv run create_coordinator.py   # writes .coordinator_id
```

Nothing drives them afterwards. The gallery doesn't use them: `ui/pipeline.py` calls
the Messages API directly and builds the same field guide locally. Treat this lane as
provisioning for the preview, not as how the product runs.

## The animation, briefly

Flat parts cut from the drawing, hinged at joints, drawn on a canvas. Paper Mario,
or Monty Python's cutouts.

Two things carry it. First, the alpha-key has to remove the paper without eating
the child's linework, which is fussier than it sounds: white-balance the
photograph, derive the ink cutoff per image, close hard before filling, and never
open (opening erases thin pencil strokes). Second, every part polygon must overlap
into its parent past the pivot, so rotating it never reveals a gap — which is why
nothing needs inpainting.

Heading 0 faces left, the direction most kids draw. Turning sweeps through the
edge-on angle where the cutout goes flat and vanishes for a frame. That
flat-paper pivot is the charm; it isn't a bug to smooth out.

## Tests

```bash
uv run pytest
```

The Creature Spec eval suite runs offline against checked-in fixtures, no API key:

```bash
uv run evals/run_evals.py
```
