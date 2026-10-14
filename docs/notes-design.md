# Notes: footnotes and endnotes

**Status: design in progress; nothing implemented.** This is the working design document for
*notes* in Guffin: footnotes, endnotes, and invisible endnotes, authored in Roam and rendered in
every output format. It records the current state, the requirements, the open design questions,
and the decision log. Decisions are recorded in [Decisions](#decisions) as they are made; until a
question appears there, it is open.

Companion docs: [publishing-semantics.md](publishing-semantics.md) (the `element-type::`
vocabulary, which already names an `endnotes` section), [render-pipeline.md](render-pipeline.md)
(where note collection and rendering would run), [roam-md.md](roam-md.md) (Roam markup Guffin
parses).


## Why

Roam has no native notes. Its building blocks are block references (`((uid))`), whose content
pops up on hover, and aliased block references (`[label](((uid)))`), which show a label in the
text. The Roam Depot **Footnotes** extension (Fabrice Gallet,
[repo](https://github.com/fbgallet/roam-extension-footnotes), v6 July 2026) assembles them into
numbered footnotes: a numbered alias at the call site, the note as a block under a `#footnotes`
header at the bottom of the page, automatic renumbering, named notes (`[^name]`), and conversion
from Markdown footnote syntax.

Guffin cannot express a note in any output today, so a Roam author has no way to publish one.


## Current state (as of `93344d1`)

- **An `endnotes` section label, nothing more.** A heading tagged `element-type:: endnotes`
  ([chicago_structure.py](../src/guffin/model/chicago_structure.py)) is placed in back matter,
  left unnumbered, and stamped `epub:type="endnotes"` in EPUB
  ([epub_semantics.py](../src/guffin/render/epub_semantics.py)). Its content is whatever the
  author writes by hand.
- **No note element.** Guffin never emits Pandoc's `Note`, the element Pandoc's writers turn into
  footnotes or endnotes.
- **No authoring syntax.** Markdown footnotes (`[^1]`) are not recognized.
- **The Footnotes extension's output breaks.** Guffin has no pattern for an aliased block
  reference. Its block-reference rewrite (`convert_block_link`,
  [roam_md_to_pandoc_md.py](../src/guffin/transcribe/roam_md_to_pandoc_md.py)) replaces the
  inner `((uid))`, leaving a nested link; Pandoc reads `[1]([note text](x-guffin:vertex/<uid>))`
  as a link labelled `1` with a garbage destination. The note block itself renders as an ordinary
  paragraph wherever it sits. (From the code plus one Pandoc run, not a full export.)


## Kinds of note

Chicago's vocabulary, which the rest of this document uses:

- **Footnote:** a note at the foot of the page, called by a reference mark (usually a superscript
  number) in the text.
- **Endnote:** the same, but collected at the end of the chapter or of the book. A back-of-book
  Notes section groups notes by chapter, and its running heads often read "Notes to Pages
  112–118".
- **Invisible endnote** (Chicago 17th ed., 13.57, "notes keyed to page numbers"): an endnote with
  no reference mark. Each note opens with the page number and a short lead-in phrase quoted from
  the passage (`41 *a 52-minute run*: Williams and Kilburn, …`). The text reads uninterrupted.
- **Short and full forms:** a short-form note (author, short title, page) against a full one. A
  work may print short notes and publish the full set elsewhere.

What each format offers natively:

| | Footnotes | Endnotes | Page numbers |
|---|---|---|---|
| **PDF (Typst)** | native `footnote()`; Pandoc's Typst writer maps `Note` to it | none native; must be generated | known at layout; a label's page is queryable (to verify) |
| **EPUB 3** | `noteref` links to `footnote` asides; reading systems may show a popup (to verify per reader) | Pandoc collects notes per chapter file (to verify) | none |
| **GFM** | `[^1]` footnote syntax, rendered by GitHub | n/a: GitHub renders all footnotes at the end of the file | none |


## Requirements

Proposed, not yet agreed. The first user is a book whose style guide calls for invisible endnotes,
full in the digital editions and shortened in print; those requirements are marked *(book)*.

- **R1 — Notes live in Roam as blocks.** A note is authored in the graph, editable there, and
  never exists only in an export.
- **R2 — One note, every format.** The same authored note renders in PDF, EPUB, and Markdown.
- **R3 — Selectable note style.** Footnotes, endnotes, or invisible endnotes, chosen per export
  or per work, not per note. *Deferred: the first implementation has one style (see
  [Decisions](#decisions)).*
- **R4 — Invisible keys.** *(book)* In PDF an invisible note is keyed by page number and lead-in;
  in formats without pages, by section title and lead-in.
- **R5 — Short and full forms.** *(book)* A note may carry a short form; an export chooses which
  form to render.
- **R6 — Interoperate with the Footnotes extension.** An author using the extension gets correct
  output without rewriting their notes. (Proposed; see Q1.)
- **R7 — Validation.** Dangling references, orphan notes, and ambiguous lead-ins are reported, in
  keeping with Guffin's existing validation passes.


## Open questions

### Q1 — Authoring syntax

*Decided: option (d′) (see [Decisions](#decisions)).* How a note and its call site are written
in Roam. Options:

- **(a) The Footnotes extension's form:** an aliased block reference at the call site, the note
  block under a `#footnotes` header on the same page. Familiar to Roam users and tool-assisted;
  the alias label is a number or a name.
- **(b) Markdown footnotes:** `[^label]` in the text, a `[^label]: …` definition block. Portable,
  but Roam shows it as plain text, with no hover or navigation. The extension converts (b) to (a).
- **(c) A tagged child block:** the note is a child of the block it annotates, marked by an
  attribute (e.g. `note::`). No call-site mark at all; the lead-in must then be stated in the note.
- **(d) The alias label *is* the lead-in:** form (a) with the label set to the passage's opening
  words: `[a 52-minute run](((uid)))`. In Roam the phrase is a live link whose hover shows the
  note; in an invisible-notes export the label renders as plain text and supplies the lead-in;
  in a footnote export the label renders as text followed by the reference mark.
- **(d′) The lead-in as a named-note label:** option (d) with the label in parentheses,
  `[(a 52-minute run)](((uid)))`, the form of the Footnotes extension's named notes. The
  parentheses tell a note marker from an ordinary aliased block reference, and the extension
  manages the note (ordering, deletion); Roam shows the parentheses in the running text.

**Observed: what the Footnotes extension writes (option (a)).** Tested 2026-10-14 on the SCFH
graph's `[[Test Article]] 4` page, with the extension's superscript setting off and its other
settings at their defaults. Two notes were inserted, the second with text selected first:

```
- This block has a footnote anchor right here->[(1)](((Mc-JWCvWX))) This is a sentence …
-  The anchor->[(2)](((AxMU9z6fm))) The following sentence
- #footnotes                                        (numbered children view)
  - This is the prose of the footnote.                                      (Mc-JWCvWX)
  - This block has a footnote that was created with text selected first.   (AxMU9z6fm)
```

- **The marker** is a plain aliased block reference, `[(n)](((uid)))`. The parentheses around
  the label are what the extension recognizes as its own; with the superscript setting on it
  wraps the marker as `#sup^^…^^`. A named note's marker is `[(name)](((uid)))`.
- **The notes** are ordinary blocks, children of a header block that the extension creates as
  the page's last top-level block. The header's text is a user setting (`#footnotes` by
  default). The header uses Roam's numbered children view, so the displayed "1." and "2." are
  not in the note text.
- **Notes are page-scoped.** Each page gets its own header, and numbering restarts at 1 on each
  page, so a document assembled from embedded pages carries several headers and several
  sequences.
- **Selecting text before inserting moves that text into the note.** It is cut from the
  sentence (here leaving a stray leading space), so a selection cannot serve as a lead-in.
- **Each note block is referenced exactly once,** by its marker: the link from note to passage.

What Guffin would need for option (a):

- recognize the marker `[(label)](((uid)))` (today it becomes a malformed nested link; see
  [Current state](#current-state-as-of-93344d1));
- recognize note blocks and keep them out of the running text, identifying a note as a block
  referenced by a marker rather than by the header's text, which is configurable;
- drop the header blocks, wherever an embedded page brings one in;
- take the lead-in from elsewhere (Q2): the marker carries none. For note 1, the natural
  lead-in is the words just before the marker.

**Observed: a hand-typed named marker with spaces (option (d′)).** Same page, same day. A third
note was made with the extension, and its marker's label was then edited by hand to
`(ANCHOR NAME)`:

```
- This block has a footnote that uses a named anchor. This is the lead-in to the anchor->[(ANCHOR NAME)](((Tk7FpgzQa)))
- #footnotes
  - …notes 1 and 2…
  - This is the footnote corresponding to the named anchor.               (Tk7FpgzQa)
```

The extension's *Reorder footnotes on current page* command left everything as it was: the
label kept its text, notes 1 and 2 kept their numbers, and the named note stayed after the
numbered ones. This matches the extension's source, which classes any label that is not all
digits as a named note: its marker is never rewritten and its note is listed after the numbered
notes. So a label carrying a phrase with spaces is accepted as a named note, which is what
option (d′) needs.

A follow-up moved the named marker's block above the block holding `(2)` and reordered again.
The call sites now read `(1)`, `(ANCHOR NAME)`, `(2)` in page order; `(2)` kept its number (a
named note takes no number), and under `#footnotes` the named note stayed last, after notes 1
and 2. So the header's order is not reading order once named notes are mixed in: the extension
lists named notes after all the numbered ones. **Guffin must order notes by the position of
their markers in the text, never by their order under the header.**

### Q2 — The lead-in

*Decided with Q1: the lead-in is the marker's label (see [Decisions](#decisions)).* For
invisible notes: where the lead-in phrase comes from. Stated by the author in the note,
derived from the call site's surrounding text, or carried by the call site itself (Q1 (d)).

### Q3 — Choosing the style

*Deferred with R3.* Where R3's choice lives: a `guffin-meta::` key on the work, a request field (`notes:
footnotes|endnotes|invisible`), a project-type default, or a combination with a precedence order.

### Q4 — Endnote placement

Partly decided (see [Decisions](#decisions)): endnotes only, in one back-matter section that
the author creates as an `element-type:: endnotes` heading and Guffin fills. Still open: how
the notes inside that section are grouped and headed (by chapter, and with what heading text and
level), and whether PDF running heads carry "Notes to Pages …".

### Q5 — Short and full forms

How a short form is authored (a child of the note block, an attribute, a convention within the
note's text) and how an export selects it (per format, per request).

### Q6 — Pandoc model

Visible notes map to Pandoc's `Note`. Invisible notes have no Pandoc element: an anchor in the
text (an empty `Span` with an id) plus a generated Notes section, finished per format by a Lua
filter or post-processing. Which layer builds the Notes section, and how the PDF learns each
anchor's page.

### Q7 — EPUB behavior

Popup footnotes versus linked endnotes, and for invisible notes, whether each note links back to
an anchor in its passage (one-way: the text carries no mark to link from).

### Q8 — Markdown behavior

Whether GFM output uses GitHub's `[^1]` footnotes for every style, and how invisible notes key to
sections there (heading links, as block references to headings already do).

### Q9 — Validation rules

Which conditions are errors and which warnings (R7), and whether a lead-in must be unique on its
page or in its section.


## Decisions

Resolved 2026-10-14:

- **Endnotes only, initially (Q4).** Guffin supports endnotes and not footnotes. Footnotes may
  come later.
- **Invisible endnotes only, initially.** The first implementation supports only invisible
  endnotes: no reference mark in the text, each note keyed by its lead-in. Endnotes with
  reference marks may come later. With a single style, R3 and Q3 are deferred.
- **One authored Notes section (Q4).** Endnotes appear in a dedicated back-matter section. The
  author must create it explicitly, as a heading tagged `element-type:: endnotes` in the back
  matter, and Guffin fills that heading with the notes. Without such a heading, no endnotes
  appear in the output.
- **Authoring syntax: option (d′) (Q1).** A note's call site is an aliased block reference
  whose label, in parentheses, is the lead-in phrase: `[(a 52-minute run)](((uid)))`. The words
  of the label are part of the sentence; the note is the referenced block, under the Footnotes
  extension's header. The parentheses identify the marker as a note (not an ordinary aliased
  block reference), and the extension treats it as a named note, ordering and deleting it.
  Chosen over (a) because a numbered marker carries no lead-in, which would then have to be
  guessed from the preceding words or copied into the note, where it goes stale; over (d)
  because (d) needs a second rule to recognize a marker and loses the extension's bookkeeping.
  Accepted cost: Roam shows the parentheses in the running text.
- **The lead-in is the label (Q2).** In the output the label's text, without its parentheses,
  is set as plain text in the sentence and quoted as the note's lead-in in the Notes section.
  Still open: what Guffin does with an all-digit label such as `(1)`, which carries no lead-in
  (an error, a warning, or a derived lead-in; part of Q9).
