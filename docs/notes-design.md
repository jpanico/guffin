# Notes: footnotes and endnotes

**Status: designed and implemented.** Every open question is decided; Q7 has two reading-app
tests open. Suppressing notes (R9) is built too: see [Suppressing notes](#suppressing-notes). The note style is chosen per project type (see the note-style decision): a book keeps
invisible endnotes, an article or a manuscript numbers its notes. See [Implementation](#implementation) for what was built
and where it departs from the decisions. This is the working design document for
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
  or per work, not per note. *Met per project type: see the note-style decision.*
- **R4 — Invisible keys.** *(book)* In PDF an invisible note is keyed by page number and lead-in;
  in formats without pages, by section title and lead-in.
- **R5 — Short and full forms.** *(book)* A note may carry a short form; an export chooses which
  form to render. *Decided as Q5.*
- **R6 — Interoperate with the Footnotes extension.** An author using the extension gets correct
  output without rewriting their notes. (Proposed; see Q1.)
- **R7 — Validation.** Dangling references, orphan notes, and ambiguous lead-ins are reported, in
  keeping with Guffin's existing validation passes.
- **R8 — Notes-only export.** *(book)* An export can produce the Notes section alone, gathered
  from the whole target, so the complete notes can be published without the text they annotate
  (the book's public repository holds the notes but not the prose). Added 2026-10-14 with Q8.
- **R9 — Notes can be suppressed.** An export can leave the notes out altogether, whatever the
  project type, format, or note style: no sign of a note at its call site, no note rendered in
  any form, no Notes section added, and an authored Notes section removed. Added 2026-10-15; see
  [Suppressing notes](#suppressing-notes).


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
- recognize note blocks and keep them out of the running text: a note is a block referenced by a
  marker (Q9 rule 7 also requires it to sit under a notes header, recognized by its text);
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

*Decided (see [Decisions](#decisions)).* Endnotes only, in one back-matter section that the
author creates as an `element-type:: endnotes` heading and Guffin fills; how the notes inside
that section are grouped and headed; whether PDF running heads carry "Notes to Pages …".

### Q5 — Short and full forms

*Decided (see [Decisions](#decisions)).* How a short form is authored (a child of the note block, an attribute, a convention within the
note's text) and how an export selects it (per format, per request).

### Q6 — Pandoc model

*Decided (see [Decisions](#decisions)).* Visible notes map to Pandoc's `Note`. Invisible notes have no Pandoc element: an anchor in the
text (an empty `Span` with an id) plus a generated Notes section, finished per format by a Lua
filter or post-processing. Which layer builds the Notes section, and how the PDF learns each
anchor's page.

### Q7 — EPUB behavior

*Decided, with two tests open (see [Decisions](#decisions)).* Popup footnotes versus linked
endnotes, and for invisible notes, whether each note links back to an anchor in its passage.

### Q8 — Markdown behavior

*Decided (see [Decisions](#decisions)).* Whether GFM output uses GitHub's `[^1]` footnotes for every style, and how invisible notes key to
sections there (heading links, as block references to headings already do).

### Q9 — Validation rules

*Decided (see [Decisions](#decisions)).* Which conditions are errors and which warnings (R7),
and whether a lead-in must be unique on its page or in its section.

### Q10 — Validation when notes are suppressed

*Decided: (a) (see [Decisions](#decisions)).* Whether the Q9 rules still run in an export with
`--suppress-notes`. Three choices:

- **(a) Skip every note check**, rules 1–7 and the orphan warning. The switch is most useful
  for a draft whose notes are unfinished, such as a book that cites notes before its Notes
  heading exists (rule 5), and checking would refuse exactly that draft. A broken marker then
  goes unreported in this export, but the next export with notes reports it.
- **(b) Keep the rules about markers' structure** (2, 6, and 7: a dangling marker, a note cited
  twice, a note outside a `#footnotes` block), and skip the rules that exist only to render
  notes (1, 4, and 5: a lead-in present, unique, and a Notes heading to hold the notes).
- **(c) Keep every rule**, so a suppressed export fails wherever the same export with notes
  would.

Recommendation: (a). The checks protect rendered notes, and a suppressed export renders none.
(b) would still refuse a draft whose notes point at blocks not yet written, a case the switch
should serve.

### Q11 — Blocks limited to a note form

*Decided: (a) (see [Decisions](#decisions)).* What happens, in a suppressed export, to a block
tagged `note-form:: short` or `note-form:: full` that stands outside a Notes section. Inside one, it goes with the section.
Three choices:

- **(a) Drop both.** Such a block, like the repository line in a Notes intro, exists for an
  edition that has notes, and a suppressed export has none.
- **(b) Keep the `full` ones**, treating the suppressed export as the default (full) edition
  without its notes.
- **(c) Keep both**, ignoring the tag, as an export with no notes has no form to choose.

Recommendation: (a). The tag means "only in the edition with these notes", and no edition with
notes is being produced.


## Implementation

Built in phases, each a commit.

- **Transcription** (`c822db2`): `roam/markdown.FOOTNOTE_MARKER_RE` and `FOOTNOTES_HEADER`;
  `NodeType.FOOTNOTES_BLOCK`; `transcribe/roam_md_to_pandoc_md.convert_footnote_markers` (before
  `convert_block_link`); `VertexLinkKind.NOTE`; `VertexType.NOTES` / `NotesVertex`.
- **Validation** (`0f6d531`): `model/notes.py` (note links in the render-visible document, and
  `placed_note_citations`, every note link in reading order with the headings governing it);
  rules 1, 2, 6, and 7 in `validate_semantics`; rule 3 as a warning in the fetch pipeline; rule 4
  (`lead_ins_unique_within_sections`) in `export-roam-tree` after the profile resolves.
- **Rendering**: `render/notes_rendering.py` builds the Notes section into the shared Pandoc
  document (`insert_notes_section`) and renders each lead-in in the running text per format
  (`note_lead_in_renderer`, passed to the link resolver as `make_doc_resolver(note_lead_in=…)`);
  rule 5 runs in `export-roam-tree` beside rule 4. The end-of-document colophon is never in the
  Pandoc document: Markdown and EPUB place it after the writer runs, so it follows a Notes section
  and the footnotes of numbered notes alike. The PDF template opens a page at a chapter or
  part heading only when the heading is in the outline, so an unlisted group heading opens none;
  the EPUB stylesheet styles `a.guffin-note-ref` and `a.guffin-note-backlink`; the Markdown slug
  check leaves the generated group headings out of its collision count. In the PDF, each lead-in
  in the running text is wrapped in the template's `note-ref` function, which underlines it unless
  `PdfRenderOptions.note_ref_underline` is off (the CLI's
  `--note-ref-underline/--no-note-ref-underline`, passed to the template as the
  `no-note-ref-underline` variable), and each group heading in its `notes-group-heading` function,
  which sets it as a subhead; the `cfg.note-ref-*` and `cfg.notes-group-*` keys in `base_cfg.typ`
  hold both styles. The EPUB stylesheet sets `h1`–`h6.guffin-notes-group` as the same subhead.
- **Options**: `NoteForm` (`full`/`short`) and the `note-form::` block tag
  (`PublishingSemantics.NOTE_FORM`, checked by `all_note_form_values_legal`); each renderer prunes
  the blocks tagged with the other form (`drop_other_note_forms`, beside `drop_unpublished`), and
  `insert_notes_section` builds each entry from the note's `short` child in a short export. The
  render options `note_form` and `notes_only` are the CLI's `--note-form` and
  `--notes-only/--no-notes-only`, and so the server's `note_form` and `notes_only` request
  fields. A notes-only export's filename gains a `.notes` segment, and it aborts when there is no
  Notes heading and none to be added.
- **Note style**: `StructuralPolicy.note_style` (`render/project.NoteStyle`) is
  `invisible-endnotes` for `book` and `numbered` for `article` and `manuscript`.
  `notes_rendering.prepare_notes` follows it: for invisible endnotes it builds the Notes section
  (`insert_notes_section`) and renders lead-ins per `note_lead_in_renderer`; for numbered notes it
  leaves the document alone and renders each note link as its lead-in and a native Pandoc `Note`
  (`native_note_renderer`), dropping a lead-in that is only a number. `export-roam-tree` runs the
  checks only invisible endnotes need (lead-ins present and unique, a Notes section present)
  only for that style, and refuses a notes-only export of numbered notes.
- **Suppressing notes**: `RenderOptions.suppress_notes`, the CLI's
  `--suppress-notes/--no-suppress-notes`; `publishing_semantics.drop_notes` with
  `notes.strip_note_links`, and `check_notes=False` through the fetch pipeline to
  `validate_semantics`. See [Suppressing notes](#suppressing-notes).

Departures from the decisions, and behavior found while building:

- **Note order comes from the model.** Q6 has the render phase walk the `NOTE` links of the built
  document. The Notes section is instead ordered by `placed_note_citations`, a reading-order walk of
  the vertex tree that descends into an embed at its site, so it yields the same order across every
  embedded page. The section has to be built *before* the links resolve anyway: each entry copies
  its lead-in from the unresolved note link, and the resolver needs to know which notes have an
  entry before it links a lead-in to one.
- **A group heading in a numbered book lacks its chapter number.** Pandoc numbers headings when it
  writes the output, after the group headings are built, so a group heading repeats the chapter's
  text but not its number. Unnumbered books, and books whose chapter titles carry their own number,
  are unaffected.
- **The note-form tag works on any block, as `publish::` does.** Q5 framed it as marking a note's
  short form and limiting an intro block; it is implemented generally (a block tagged with one form
  appears only in exports of that form), so the two uses are the same rule.
- **A notes-only export drops the end-of-document colophon.** The document is cut down to its
  title and the Notes section; Markdown's revision line, inserted afterwards, still appears.
- **The colophon is always last** (Joe, 2026-10-14). Pandoc's GFM and EPUB writers set numbered
  notes after the body's last block, which put them below a colophon built into the document. The
  colophon is therefore placed after the writer runs: Markdown includes it with
  `--include-after-body`, which puts it after the footnote definitions, and EPUB appends it to the
  last document in reading order after packaging, since an after-body include is repeated in every
  EPUB content document. GitHub, VS Code's preview, and Typora's HTML and PDF export gather a
  Markdown file's footnotes at the bottom of the rendered page wherever the definitions sit, each
  under a rule of its own, so there the colophon still renders above the notes; only notes Guffin
  numbered itself could avoid that. Typora's editor shows the definitions where they sit, after the
  body with no rule between. A rule written into the file was considered and rejected (Joe,
  2026-10-14): in the gathering viewers it would land on the colophon's own rule.
- **In a parts book, the EPUB gives each chapter's notes a file of its own.** Pandoc splits an EPUB
  at the chapter level, level 2 in a parts book, and a Notes heading promoted to part level puts its
  chapter groups at level 2. Each file is back matter, the links between files resolve, and the
  group headings stay out of the navigation, so each chapter's notes open on a fresh screen.


## Suppressing notes

*Designed and built 2026-10-15.* R9's switch: an export that leaves the notes out altogether.
Everything here is decided (see [Decisions](#decisions)), including how it treats validation
(Q10) and blocks limited to a note form (Q11).

**The switch.** `RenderOptions.suppress_notes`, default `False`, is the CLI's
`--suppress-notes/--no-suppress-notes` and so the server's `suppress_notes` request field. It is
named and shaped like `--suppress-attributes`: a plain switch, off by default, with no
environment variable. It applies to every project type, every output format, and either note
style.

**What it removes.** With the switch on:

1. **No sign of a note at its call site.** Each note marker renders as its lead-in alone, as
   plain running text: no number, footnote, endnote reference, link, span, or anchor. A lead-in
   that is only a number, the Footnotes extension's default label, renders as nothing, and so do
   the spaces directly before it, so no gap is left in the sentence (unless a letter or digit
   follows the marker directly, when one space stays so two words do not join). The superscript
   form (`#sup^^…^^`) is a marker like any other.
2. **No note is rendered.** Neither style runs: invisible endnotes build no entries, and numbered
   notes produce no Pandoc `Note`, so no format has footnotes or endnotes.
3. **No Notes section is added.** Guffin adds a Notes section only by filling an authored one,
   and with the switch on it fills nothing.
4. **An authored Notes section is removed.** Every heading tagged `element-type:: endnotes` is
   pruned with its whole subtree before rendering, as `publish:: false` prunes a block, so its
   intro goes too. So are the `#footnotes` blocks and the notes under them. Those already render
   nothing where they sit, but pruning them keeps a note's contents, such as an image, out of the
   asset fetch.

**How it meets the other options.**

- With `--notes-only` it asks for nothing, and it is refused, as a notes-only export of numbered
  notes is.
- `--note-form` has no notes to choose a form of, and it is ignored. A block tagged with either
  form (`note-form:: short` or `full`) is dropped wherever it stands (Q11).
- No note check runs (Q10): not the Q9 rules, which would otherwise refuse a draft whose notes are
  unfinished, and not the orphan-note warning. A broken marker goes unreported in a suppressed
  export, and the next export with notes reports it.
- The output filename does not change, as it does not for `--suppress-attributes`, so a
  suppressed export replaces an unsuppressed one of the same target, type, and format.
- A plain block reference `((uid))` to a note block, as opposed to a marker, is an ordinary
  reference. With the notes pruned, it renders as its display text with a warning, as a reference
  to any pruned block does.

**Where it lives.**

- **The model does it all:** `model/publishing_semantics.drop_notes(tree)`, beside
  `drop_unpublished` and `drop_other_note_forms` and sharing their `_drop_subtrees`. Its seeds are
  every `NotesVertex`, every heading of element type `endnotes`, and every block tagged with either
  note form. Then `model/notes.strip_note_links` reduces every note link left in the text to plain
  text: the lead-in stays, a numbered one goes. Each renderer applies `drop_notes` when the option
  is set, in place of `drop_other_note_forms`, and the rest of rendering never sees a note link.
- **One test for a numbered label:** `model/notes.is_numbered_lead_in`, which validation rule 1,
  the numbered-notes renderer, and `strip_note_links` all use.
- **Validation:** with the option set, `export-roam-tree` skips its note checks (Q9 rules 1, 4,
  and 5), the vocabulary pass skips the note validators (rules 2, 6, and 7), and the fetch
  pipeline skips the orphan warning (rule 3). `all_note_form_values_legal` still runs: a malformed
  `note-form::` value is a vocabulary error, not a note.
- **Tests:** each behavior above, for both note styles and all three formats; the notes-only
  refusal; a book with notes and no Notes heading exporting cleanly (Q10); and blocks of either
  note form dropped (Q11).

**Departure from the design: the links are stripped in the model.** The design had
`prepare_notes` take the option and return a third lead-in renderer that rendered each note link
as its bare lead-in. That cannot work once the notes are pruned. A note link whose note is gone
is dangling, and the link resolver leaves a dangling link as its display text with a warning
without consulting any renderer. So a numbered label printed as its number, and every note link
logged a warning. Reducing the links in the model, before the Pandoc document is built, removes
both problems. It also covers a note link reached through a block reference, which the
render-time pass could not see.


## Decisions

Resolved 2026-10-14:

- **Endnotes only, initially (Q4).** Guffin supports endnotes and not footnotes. Footnotes may
  come later.
- **Invisible endnotes only, initially.** The first implementation supports only invisible
  endnotes: no reference mark in the text, each note keyed by its lead-in. Endnotes with
  reference marks may come later. With a single style, R3 and Q3 are deferred. (In electronic
  formats the lead-in itself may be a link to its note, styled so it does not distract; that
  adds no mark to the text. See Q7.) *Narrowed to books by the note-style decision below.*
- **One authored Notes section (Q4).** Endnotes appear in a dedicated back-matter section. The
  author must create it explicitly, as a heading tagged `element-type:: endnotes` in the back
  matter, and Guffin fills that heading with the notes. Without such a heading, no endnotes
  appear in the output.
- **Grouping inside the Notes section varies by format (Q4).** The grouping follows the key each
  format uses to locate a note:

  | | `book` | `article` |
  |---|---|---|
  | **PDF** (key: page number + lead-in) | a group per chapter | one ungrouped list |
  | **EPUB, Markdown** (key: section + lead-in) | a group per chapter, then a subgroup per section | a group per section |

  In PDF the page number locates the passage, so chapter groups suffice (Chicago's usual
  layout). In EPUB and Markdown there are no pages: the section subheading carries the section
  half of the key once for all its notes, and each entry under it needs only its lead-in. In
  Markdown the subheading can link to the section itself (Q8).
- **What a group heading says and where it sits (Q4).** A group heading repeats the rendered
  text of the chapter or section heading it stands for, unchanged; Guffin generates no new
  numbering or names. Groups follow document order, and a chapter or section with no notes gets
  no group. Group headings sit one level below the Notes heading (sections one below chapters)
  and are kept out of the table of contents and the EPUB navigation (Pandoc's `unlisted` class;
  whether the Typst path honors it is to be verified).
- **"Section" means the heading one level below the chapter (Q4).** In a `book`, that is
  Guffin's `section` level; in an `article`, the top-level heading. A note inside a deeper
  subsection belongs to the section that contains it, and a note before a chapter's first
  section belongs to the chapter itself, listed under the chapter heading ahead of its section
  subgroups. This is also the unit of Q9 rule 4 (a lead-in must be unique within its section).
- **Running heads unchanged (Q4).** Guffin's PDF header today is the same on every page (title
  and revision); it has no section-aware running heads. The Notes pages keep that header.
  Section-aware running heads, including "Notes to Pages 112–118", are deferred.
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
  An all-digit label such as `(1)` carries no lead-in; Q9 makes it an error.
- **A short form is a marked child of the note (Q5).** The note block holds the full form. Its
  short form, when it has one, is a child block marked through Guffin's existing `guffin-meta::`
  mechanism (the pattern of `pdf-render::` and `code-language::`):

  ```
  - F. C. Williams and T. Kilburn, "Electronic Digital Computers," Nature 162 (1948): 487.
    - Williams and Kilburn, "Electronic Digital Computers," 487.
      - guffin-meta::
        - note-form:: short
  ```

  The note's other children are continuation paragraphs of the full form. Rejected
  alternatives: Roam block versions (versions carry no names, so Guffin could not tell short
  from full); a `short::` attribute (ordinary attribute values must be slugs, and
  `guffin-meta::` values cannot contain commas, which citations are full of); generating short
  forms from structured citations (citation management, a separate and much larger project).
- **The export chooses the form (Q5).** A request option `note_form`, `full` or `short`
  (default `full`), chosen per export rather than per format, since a PDF may be a print
  edition or a reviewer copy. In a `short` export, a note without a short form prints its full
  form, without a warning: many notes are already short.
- **The Notes section may carry an intro (Q5).** Blocks the author writes directly under the
  `element-type:: endnotes` heading are kept, ahead of the generated groups. An intro block
  marked `note-form:: short` or `note-form:: full` (through `guffin-meta::`, as above) appears
  only in exports of that form, so a print edition can say where the complete notes are
  without the digital edition repeating it.
- **A marker transcribes to a `NOTE` vertex link (Q6).** A new `VertexLinkKind.NOTE`, path stem
  `vertex-note`, joins `REFERENCE` and `EMBED` in `model/vertex_link.py`. A new inline converter
  rewrites the marker, label without its parentheses as the display:

  ```
  [(a 52-minute run)](((Tk7FpgzQa)))   →   [a 52-minute run](x-guffin:vertex-note/Tk7FpgzQa)
  ```

  It runs in `to_pandoc_md` before `convert_block_link`, as `convert_page_link_aliases` runs
  before `convert_page_link`, so the inner `((uid))` is never rewritten into a nested link.
  Transcription records only the meaning (this phrase is the lead-in of note X); what it becomes
  is decided per format in the render phase, as for the other two kinds. Chosen over emitting a
  Pandoc span with an id at transcription, which would have put a rendering choice into
  transcription.
- **The notes header becomes a `NOTES` container vertex (Q6).** A new `VertexType.NOTES`
  classifies the header block (recognized by its text, `#footnotes`; see rule 7): its content is
  a set of notes, as a `TABLE` vertex's children are its rows. The notes themselves stay
  ordinary vertices (`TEXT` and so on), since what makes a block a note is its role, not its
  content; a per-note vertex type would flatten or duplicate the existing content types. The
  renderer renders nothing for a `NOTES` vertex where it sits, which takes the header and its
  notes out of the running text wherever an embedded page brings one in. The model has no
  separate list of notes: the notes are the `NOTES` children, reached through the `NOTE` links.
- **Validation hooks (Q6).** Rules 1, 2, 4, 6, and 7 run on the model, finding markers by
  parsing `x-guffin` URLs: rule 7 is "a `NOTE` link's target is a child of a `NOTES` vertex",
  and rule 3 is "a `NOTES` child no `NOTE` link targets". Rule 5 runs in the render phase.
- **The render phase resolves `NOTE` links and builds the Notes section (Q6).**
  - **Order.** `resolve_vertex_links` resolves links after embeds are expanded, so walking the
    `NOTE` links of the built document yields the notes in reading order across every embedded
    page, which is the order the decisions above require.
  - **Anchors.** A `NOTE` resolver replaces each link with the lead-in as plain text plus a
    format-specific anchor at its start: in Typst, a zero-width `#metadata(none)` carrying the
    label `<guffin-note-<uid>>`; in EPUB, an element with the id `guffin-note-<uid>`; in
    Markdown, per Q8.
  - **The section.** In the shared Pandoc document, the `element-type:: endnotes` heading is
    filled with the intro blocks (filtered by `note_form`), the group headings (unnumbered and
    unlisted, grouped by format), and one entry per note: a `Div` (class `guffin-endnote`)
    holding a locator placeholder, the lead-in in italics, ": ", and the note in the chosen
    form.
  - **Locators.** The Typst filter turns each placeholder into
    `#context counter(page).at(<guffin-note-<uid>>).first()`, the displayed page number of the
    passage; the other formats drop it.
  - **No Pandoc `Note`.** Pandoc's `Note` element is always a visible note, which these are
    not; it remains the path for footnotes or visible endnotes later.

  Verified 2026-10-14 (Pandoc 3.8.3, Typst 0.14.2): Pandoc writes a span's id as a Typst label,
  and `counter(page).at(<label>)` in a later Notes section returns the labelled passage's
  displayed page number. Typst attaches a label to the element before it, which can be the
  whole run of text from the start of the sentence, so a paragraph crossing a page break could
  report the wrong page; hence the explicit zero-width anchor at the start of the lead-in
  rather than Pandoc's label.
- **Notes and passages link both ways in electronic formats (Q7).** The reason for invisible
  notes is print, where any mark at the passage is visible on the page; an electronic format
  can link without distracting. So:
  - **Note → passage.** In each Notes entry the locator and lead-in link to the passage's
    anchor (`guffin-note-<uid>`): in EPUB the italic lead-in, in PDF the page number. The
    reading app's own Back command returns to the notes. Verified 2026-10-14 (Pandoc 3.8.3):
    in a two-chapter EPUB, Pandoc rewrote `#guffin-note-<uid>` to `ch001.xhtml#guffin-note-<uid>`
    by itself, so links across chapter files need no work in Guffin.
  - **Passage → note.** The lead-in in the running text links to its Notes entry, which
    carries the id or label `guffin-endnote-<uid>`.
  - **PDF styling.** A PDF link is an annotation laid over the page, not ink, so an unstyled
    link is invisible on screen and in print yet clickable. Guffin's template styles only links
    to URLs (`abstract.typ`), so internal links are unstyled already. The note → passage link
    (the page number) stays unstyled. The passage → note link takes the EPUB's subtle style by
    default, and `--no-note-ref-underline` (the request field `note_ref_underline: false`)
    leaves it unstyled for a print export; the link is still there, unseen. *Amended
    2026-10-15:* this was decided the other way round, unstyled by default with an option to add
    the style; see the decision of that date.
  - **EPUB styling.** The passage → note link is styled to hint, not to look like a hyperlink:
    the text keeps its normal color, with a thin dotted underline in a muted gray set slightly
    below the baseline.
  - **No special EPUB semantics on entries, for now.** The Notes section is already
    `epub:type="endnotes"`; each entry is a plain `div`, not an `aside`, with no
    `epub:type="footnote"` or `"endnote"`, because some reading apps hide elements so marked
    from the normal flow.

  Open items, to be tested in Apple Books (and any other reading app that matters) before the
  EPUB treatment is final:
  1. **Link styling survives.** Whether the reading app keeps the subtle style or applies its
     own link color or underline over the publisher's CSS (Kindle notably does).
  2. **Pop-up notes.** Whether marking the passage → note link `epub:type="noteref"` and the
     entry as a note makes the app show the note in a pop-up in place, and whether doing so
     hides the entries from the Notes section. If pop-ups work and the section stays visible,
     they replace the plain link.
- **Markdown links a note to its section only (Q8).** In a Markdown export of a whole document:
  - **No GitHub footnotes.** GFM's `[^1]` renders a visible superscript number and a list at
    the end of the file, a visible-marker style that invisible notes exclude.
  - **Grouping as Q4:** by chapter, then by section.
  - **Each section group heading links to its section,** by the GitHub-style slug Guffin
    already uses for links to headings (`[The First Program](#the-first-program)`), with no
    HTML.
  - **No passage anchors and no passage → note links.** GitHub strips styling, so a lead-in
    link in the prose would show as a plain blue link: the mark invisible notes avoid. The EPUB
    and PDF are the reading editions; Markdown keys a note to its section and no further.

  Implementation note: a group heading repeats its section's title, so the same heading text
  appears twice in one file. Guffin treats two headings with the same slug as a collision and
  falls back to HTML `vertex-<uid>` anchors for both; the generated group headings must be
  left out of that check, or every noted section heading would gain an HTML anchor.
- **A `notes_only` export option (Q8, R8).** The export reads the whole target as usual, gathers
  its notes, and outputs only the Notes section: the endnotes heading, its intro blocks (by
  `note_form`), the group headings, and the entries. Section group headings are plain text,
  since the sections they would link to are not in the output. In a `notes_only` export a
  missing `element-type:: endnotes` heading is an error whatever the project type, since there
  is nothing else to output (amended below: only when no Notes section is added either). The option applies to every format; its first use is a Markdown
  export of a book's complete notes for publishing beside the book's code.
- **A missing Notes section is added, except in a book (rule 5 amended).** *Superseded the same
  day by the note-style decision below: articles and manuscripts no longer keep invisible
  endnotes, so they need no Notes section, and this mechanism was removed.* Rule 5 first had an
  `article` or `manuscript` export warn and leave its notes out. Instead, the project profile's
  `StructuralPolicy` carries `add_missing_notes_section`: on for `article` and `manuscript`, off
  for `book`. When it is on and the document cites notes but has no `element-type:: endnotes`
  heading, each renderer adds one before rendering (`model/notes.with_notes_section`): a heading
  titled "Notes" at the end of the root, at the shallowest heading level the document uses,
  carrying the `element-type:: endnotes` assignment a `guffin-meta::` child would make. It goes
  through the ordinary heading path, so it is back matter and unnumbered like an authored one. A
  book's Notes section is part of its designed back matter, so a book still fails without one. A
  notes-only export aborts only when it would have nothing to show: no Notes heading and none to
  be added. (Decided 2026-10-14.)
- **The note style follows the project type (supersedes the two decisions above).** A book keeps
  invisible endnotes. An article and a manuscript number their notes, the scholarly convention
  (Quarto's `manuscript` is a scholarly article): each note link renders as its lead-in followed by
  a superscript number linked to the note, placed the way each format places its own notes, a
  footnote at the foot of the page in PDF (Typst links the number and the note both ways), an
  endnote in EPUB (`noteref` to a `footnote` aside, the pairing Apple Books shows as a pop-up), a
  GitHub footnote in Markdown. A label that is only a number, the extension's own, gives way to
  the format's number. The style is `StructuralPolicy.note_style`. With numbered notes, the checks
  that exist only because invisible endnotes are keyed by lead-in (Q9 rules 1, 4, and 5) do not
  apply, and a notes-only export, which exports a Notes section, is refused. Short and full forms
  apply to both styles. (Decided 2026-10-14.)
- **Validation rules (Q9).** "Error" follows Guffin's existing posture for vocabulary checks: it
  fails `export-roam-tree` (and the server's `/v1/export`) and is logged as a warning by
  `dump-roam-tree`. "Warning" is logged and never fails anything.

  | # | Condition | Severity |
  |---|---|---|
  | 1 | A marker label with no lead-in: all digits (`(1)`) or empty (`()`) | error (invisible endnotes only) |
  | 2 | A dangling reference: the marker's target block does not exist | error |
  | 3 | An orphan note: a note block no marker references (the note is dropped) | warning |
  | 4 | Two notes in the same section with the same lead-in | error (invisible endnotes only) |
  | 5 | Notes present but no `element-type:: endnotes` heading | error (invisible endnotes only, so a `book`; amended below) |
  | 6 | One note block cited by more than one marker | error |
  | 7 | A marker whose target is not a child of a notes header block | error |

  Rule 5 is an error for `book` because a server export returns no warnings on success
  (server-mode v1), so a book's notes would otherwise vanish without a visible sign. It
  depends on the project type, so it runs where that is known (after the profile resolves), not in
  the vocabulary pass. Rule 6 exists because an invisible note annotates exactly one passage, while
  the Footnotes extension lets a named note be cited repeatedly. Rule 7 keeps a body paragraph
  from being filed as a note; the notes header is recognized by its text, the extension's
  default `#footnotes`, and making that configurable is deferred. Lead-in uniqueness is checked
  per section only; two passages in different sections that land on the same PDF page with the
  same lead-in are not detected (a known gap, detectable only after layout).

Resolved 2026-10-15:

- **Notes can be suppressed (R9).** An export can leave the notes out altogether, with
  `--suppress-notes/--no-suppress-notes` (the request field `suppress_notes`), named for
  consistency with `--suppress-attributes`: off by default, and the same for every project type,
  format, and note style. With it on, no call site shows any sign of a note, no note is rendered in
  any form, no Notes section is added, and an authored Notes section (a heading tagged
  `element-type:: endnotes`) is removed before rendering. See [Suppressing notes](#suppressing-notes).
- **No note checks in a suppressed export (Q10, choice (a)).** None of the Q9 rules runs, nor the
  orphan-note warning. The checks protect rendered notes, and a suppressed export renders none;
  keeping even the marker-structure rules (2, 6, 7) would refuse a draft whose notes point at
  blocks not yet written, a case the switch should serve.
- **Both note forms dropped in a suppressed export (Q11, choice (a)).** A block tagged
  `note-form:: short` or `note-form:: full` is dropped wherever it stands: the tag means "only in
  the edition with these notes", and no edition with notes is being produced.
- **The PDF lead-in is underlined by default (amends Q7).** In a book PDF read on screen, a
  lead-in with no mark at all is too cryptic: nothing shows the reader that it links to a note
  until the pointer changes shape over it (Joe). So the passage → note link takes the EPUB's
  style by default, a thin dotted underline in a muted gray set slightly below the baseline, and
  `--no-note-ref-underline/--note-ref-underline` (request field `note_ref_underline`) turns it
  off for a print export, where the link does nothing and the underline would be a mark in the
  text. The option applies to the PDF only: the EPUB always underlines, and Markdown never links a
  lead-in (Q8).
- **Group headings are set as subheads (Q4).** A chapter's group heading sits at the chapter
  level or one below it, so in the PDF and EPUB it took a chapter heading's display size, far too
  large for a label over a few notes (Joe). Both formats now set every group heading at the body
  size in bold, whatever its level, with space above it and kept with the entry below it.
  Markdown has no sizes to set.
