# Bug Log — creature gallery (`creature-swarm/ui`)

Found while clicking through the running gallery (`ui/serve.py`). Root causes and
fixes below; all four fixes verified against the live server.

---

## BUG-1 — "Close" on the walk screen does nothing

- **Symptom:** After clicking **▶ walk**, the walk dialog opens but the **Close**
  button doesn't return you to the gallery.
- **Repro:** Gallery → any animated creature → **walk** → click **Close**. Nothing
  happens (Escape did close it, but the button didn't).
- **Root cause:** `#dlg-x` had no click handler and wasn't inside a
  `<form method="dialog">`, so a bare `<button>` in a `<dialog>` did nothing.
- **Fix (`index.html`):** wire `#dlg-x` to `dlg.close()`, also close on backdrop
  click, and blank the iframe on close so the animation stops.
- **Status:** Fixed.

## BUG-2 — No way back from a field guide

- **Symptom:** Opening **📖 field guide** leaves you on a full page with no way
  back to the gallery.
- **Repro:** Gallery → **field guide** → no back/home affordance on the page.
- **Root cause:** the guide is a standalone HTML page (served from
  `prebuilt/<stem>.guide.html`) with no navigation, opened in a new tab that has
  no history to go back through.
- **Fix (`serve.py`):** `get_guide` now runs responses through `_present_guide`,
  which injects a fixed **← Back to gallery** link. Applied at serve time so
  every already-cached guide gets it without a rebuild.
- **Status:** Fixed.

## BUG-3 — Field guide repeats each section's title

- **Symptom:** Each section's title appeared twice (e.g. *Habitat & Ecology*
  shown as a heading, then again immediately below).
- **Root cause:** the template titles each section with an `<h2>`, and some
  specialist sections also opened with their own top-level `<h1>` of the same
  title, so it rendered twice.
- **Fixes:**
  - `serve.py` `_present_guide`: drop an `<h1>` that immediately follows an
    `<h2>` (the creature-name `<h1>` at the top is preceded by `<body>`, so it's
    untouched). Cleans **already-cached** guides at serve time.
  - `render.py`: strip a leading `<h1>` from each section body so newly rendered
    guides never double-title.
- **Status:** Fixed (live for all guides).
- **Deferred:** the original report also noted guides read ~20% too long with
  overlap across sections. Making the guides shorter is **dropped for now** at the
  team's request — no prompt/length changes. Can revisit later (would be a
  `pipeline.py` prompt/`max_tokens` change plus regeneration).

## BUG-4 — Creature name mismatch / duplicated on the walk screen

- **Symptom:** The gallery card name matches the (black-on-black) name at the top
  of the walk dialog, but both differ from the name + description at the bottom of
  the animation. e.g. card said *Flapjack*, the animation said *Fanfoot Wingbird*.
- **Root cause:** two different name sources. `/api/creatures` (card + dialog top)
  read `name` from the **rig** file (`rigs/<stem>.rig.json` → "Flapjack"), while the
  animation caption uses the **specialist agent's** name from
  `prebuilt/<stem>.spec.json` ("Fanfoot Wingbird"). The dialog also re-printed the
  name at the top, duplicating what the animation already shows.
- **Fix:**
  - `serve.py` `api_creatures`: prefer the agent's `spec.json` name (via
    `_spec_name`, which unwraps the `{common_name, mock_latin_binomial}` object),
    falling back to the rig name / stem. Now the card, walk caption, and field
    guide all show the same name.
  - `index.html`: remove the top `#dlg-name` from the walk dialog so the name
    isn't duplicated — the animation's own caption (the agent name) is the one
    shown.
- **Status:** Fixed. Verified: `bird` → *Fanfoot Wingbird*, `pig-face` →
  *Lopsided Bunny-Faced Whiskerbeast*.
