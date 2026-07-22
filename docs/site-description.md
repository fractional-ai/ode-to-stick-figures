# Site description

Functional brief for a redesign. What the site is for, who uses it, and everything it
has to let them do. Deliberately silent on how any of it should look — the current
implementation is one answer, not the requirement.

## Purpose

A child draws an animal that doesn't exist. The site takes that drawing and returns two
things: the creature **in motion**, animated from the drawing's own pixels, and a
**field guide entry** about it — biology, anatomy, diet, habitat, folklore — written
as though the animal were real and well studied.

The joke, and the whole appeal, is the collision of a wobbly crayon drawing with the
form of a natural history reference — taken completely seriously, and delighted about it. Both halves have to land. If the drawing gets
smoothed, corrected, or redrawn into something more polished, the piece stops working:
the animation is the child's own marks, hinged and set moving, and it must stay
recognisably theirs.

## Audience

Three groups, in descending order of volume:

1. **Visitors with no context** — someone sent them a link. They arrive, look at
   creatures, leave. They never sign in and never upload. Most traffic. They should
   understand what they're looking at within a few seconds and without instructions.
2. **The parent or adult who has a drawing** — they came to put a specific drawing in.
   They need to sign in, and they'll wait for a result if they know they're waiting.
3. **The child who drew it** — often watching over the adult's shoulder rather than
   driving. They care about one thing: seeing their animal move. They are not
   necessarily reading anything.

The field guide reads like an encyclopedia written for children — the form is a
reference book, but the voice is warm, curious and openly delighted by the animal,
and it explains its own hard words. Not dry, and not adult. The *interface* around
it should not assume an adult reader either.

## Content model

One **creature** is the unit. Each has:

- A **source drawing** — a photo or scan of the original, on paper.
- A **name** and a one-line **tagline**, both model-written, both part of the humour.
  Either can be long. Taglines run to a dozen-plus words and the punchline is usually at
  the end, so anything that truncates them destroys the joke.
- An **animation** — the drawing's parts, hinged and moving, looping. Called a walk
  cycle internally, but only 3 of the 13 creatures actually walk: the rest buzz,
  undulate, slither, waddle, skitter, drag, or barely move at all. Each carries its own
  `locomotion` description and the interface should not promise a gait it hasn't got.
- A **field guide** — a long document, currently ~8 sections (Specimen, In motion,
  Biology, Anatomy, Diet & Life Cycle, Notable Adaptation, Habitat & Ecology, Folklore &
  Society). Mixed prose, images, and an embedded 3D/animated view. Long enough to scroll
  substantially.

Creatures come from two places, and the distinction matters for trust and moderation but
should not necessarily be visible: **bundled** ones ship with the site and are vetted;
**uploaded** ones are user-contributed and are, by definition, not.

### Three states a creature can be in

Every creature is in exactly one, and the design needs a clear answer for each:

- **Animated** — everything worked. Walk and field guide both available.
- **Refused** — the system looked and declined, with a reason ("no animal in this
  drawing"). This happens for a painted scene, a landscape, a page of writing. **The
  refusal is a feature and should be presented as a considered judgement, not a
  failure or an error.** Showing a plausible-but-wrong animation would be worse than
  showing nothing, and the refusal reason is often funny in its own right.
- **Incomplete** — a drawing is in but has no animation yet. Neither success nor
  refusal; work that didn't finish. Currently reads as "needs a rig."

A design that only handles the happy path will look broken a meaningful fraction of the
time.

## What a user can do

**Browse the collection.** All creatures, all three states, in one view. Currently a
grid of the original drawings; the arrangement is open. Ordering should favour the
animated ones — a visitor's first impression shouldn't be a row of things that don't
move.

**Watch a creature move.** The single most important interaction, and the one the child
cares about. It's a looping animation with a caption. Currently a modal over the
collection; it does not have to be. Requirements: reachable in one action from the
collection, dismissable in one action, and the animation must actually stop when
dismissed rather than continue unseen.

**Read a field guide.** A long document, currently opened in a new tab. It has its own
internal structure and needs a way back to the collection that survives being scrolled
to the bottom of a long page.

**Submit a drawing.** Choose or drag in one or more image files. Requires being signed
in; browsing never does.

**Sign in and out.** Only ever needed to submit. A signed-out visitor should not be
nagged about it, and should never hit a login wall by accident.

## Interaction constraints that will shape the design

**Submitting takes about a minute.** Not two seconds. A real build runs a chain of
model calls — roughly 50 seconds, sometimes more, with no meaningful intermediate
progress available to report. This is the single hardest design problem on the site. A
plain spinner for 60 seconds reads as broken, and the person waiting is often standing
next to the child who drew the thing. Whatever you do here matters more than anything
on the collection view.

**Multiple files can be submitted at once**, and they process one after another, so the
waiting problem compounds.

**Submissions can be rejected**, and there are several distinct reasons: not an image,
not a drawing of an animal (the refusal above), and not-signed-in. These want different
treatments — one is a mistake, one is a verdict, one is a prompt.

**Access can be denied after sign-in.** Sign-in is restricted to specific email
domains, so a successful Google login can still end in "not allowed to upload." That's
a real state needing a real screen, not a dead end.

**Sign-in interrupts whatever the person was doing** — they were trying to submit a
drawing. They should land back where they were, not at the top of the site.

## Non-negotiables

- **The drawings must be presented as artifacts on paper.** They are ink and crayon on a
  white-ish page, photographed. They need to sit on something that reads as neutral
  ground in both light and dark presentation — a dark surface behind a photographed
  white page looks like a mistake.
- **Drawings vary wildly in shape.** Very wide (a millipede), very tall, small and
  square. Nothing should crop them or letterbox them into uniform tiles.
- **Names and taglines must be free to wrap.** See above; truncation kills the joke.
- **Keyboard and screen-reader access to every interaction**, including file submission
  and dismissing the animation view. The current build's file input is visually hidden but
  still focusable specifically so submission works without a mouse — whatever replaces
  it needs the same property.
- **Both light and dark presentation** are supported today and should stay supported.
- **Field guide content is user-influenced and cannot be fully trusted.** Uploaded guides
  are rendered in isolation from the rest of the site for security reasons, which
  constrains how tightly a guide can be integrated into surrounding site chrome. Worth
  knowing before designing a layout that assumes shared navigation, shared styling, or
  communication between the guide and the page around it. Ask before designing around
  this one.

## Open questions a designer will likely raise, and the current answers

- **Can uploaded creatures be deleted or edited?** No. There is no per-user history, no
  ownership shown, no moderation queue. Worth flagging if a design implies otherwise.
- **Is there any personalisation or account surface?** No. Sign-in exists solely to
  authorise submission. There's no profile, no "my creatures."
- **Can you link to one creature?** Field guides and animations have their own URLs.
  There is no per-creature landing page combining them.
- **How many creatures are there?** Currently 14. Design for tens, not thousands, but
  don't assume it stays at 14.
- **Is there sound?** No.
- **Mobile?** Yes, it has to work on a phone — a parent showing a child is a phone-shaped
  situation.
