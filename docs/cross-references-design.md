# Typed cross-references: figures, tables, and listings

The design for numbered figures, tables, and code listings, the captions that make them, the
references to them from the running text ("see figure 2.3"), and the lists of them in the front
matter. Status: **built in full on 2026-10-17/18 (the deferred corner of Q3 aside): the
vocabulary, model, validation, policy directive, the rendering of floats and references in all
three formats, the lists of figures and tables, and the empty-list warning (every step of the
sketch). Test Article 1 carries a figure, a listing, and a table float, each over its content
block and cited with a kind-word reference; Test Article 3 carries the same three kinds whose
content is a standalone reference to a block elsewhere on the page; Test Article 7, a parts
book, floats every image, table, and listing (Figure 1.1–3.1, Listing 4.1, Table 30.1) and
fills its authored `list-of-illustrations` and `list-of-tables` headings.**

This is the "typed cross-references" thread of
[quarto-borrowing-analysis.md](quarto-borrowing-analysis.md), named there as Guffin's biggest
gap. Companion docs: [publishing-semantics.md](publishing-semantics.md) (the `element-type::`
vocabulary this adds to), [render-pipeline.md](render-pipeline.md) (*Captions*, the current
treatment), [chicago-front-matter.md](chicago-front-matter.md) (the list of illustrations), and
[notes-design.md](notes-design.md), whose shape this follows and whose Notes section is the
precedent for a generated list.


## The word *float*

A *float* is typesetting's word for a block that is not fixed to the place in the text where it
was written: a figure, a table, or a listing is a box that must stay whole, so when it will not
fit at the foot of a page the typesetter lets it float to the next page and closes the text up
behind it. Because a float may land somewhere other than where it was authored, the text cannot
say "the figure below"; it says "figure 2.3", and the number finds it. That is why numbering,
captions, and cross-references travel together. The word is TeX's (its `figure` and `table`
are "floating environments"), kept by Pandoc and Quarto; Typst's `figure` is its float. This
document uses it as the one word for the three kinds, whether or not a format lets the box
drift: the EPUB has no pages, and Guffin's PDF leaves a figure where the author put it when it
fits.


## Why

A book's diagrams are figures: the text refers to them, a reader in chapter 6 turns back to the
one in chapter 1, and the front matter may list them. That needs three things Guffin lacks: a
figure has a **number**, a reference to it renders as that number ("figure 2.3"), and the
numbers can be gathered into a **list of figures**. Tables and code listings are the same kind of
thing, with their own series. Roam gives the author everything needed to express a reference: a
block reference `((uid))` in the running text *is* a cross-reference, and Guffin already
renders a block reference by the kind of its target. What is missing is the typed rendering and
the numbering behind it.

The SCFH book has two diagrams today and will have more; its illustrations by Emi Panico are a
different kind of picture, chapter art with no caption, which Chicago would neither number nor
list (see [chicago-front-matter.md](chicago-front-matter.md) on lists of illustrations). The
design must tell the two apart.


## Current state (as of `b8b68ed`)

- **No figure in the vocabulary.** `StructuralElement` has `list-of-illustrations` (the
  front-matter section that would list figures, mapped to EPUB `loi`) and `table-of-contents`,
  but no figure, table, or listing element, no caption attribute, and no figure number.
  `AttributeAnchor` has no image or table anchor; the only block-kind anchors are `PDF` and
  `CODE_BLOCK`.
- **No figure in the render build.** An `ImageVertex` renders as a Pandoc `Image` in a plain
  `Para`; a `CodeBlockVertex` as a `CodeBlock`; a `TableVertex` as a `Table` with an empty
  caption. The children of an image or listing render as a `caption`-classed `Div` beneath it
  (`_caption_blocks`), which each format styles as a caption. Pandoc never sees a `Figure` or a
  table `Caption`, so nothing is numbered and nothing can be listed. A table has no caption at
  all: its children are its rows.
- **A standalone reference displays its target.** A text vertex whose entire content is one
  reference to a block-level vertex (image, PDF, code block, callout, quote, table) renders as
  that block (`_referenced_block_blocks`, `_BLOCK_LEVEL_VERTEX_TYPES`). This is how a figure
  kept on a collection page appears in a chapter, as the epigraphs do.
- **An inline reference degrades by kind.** A reference amid text (`make_resolver`) renders an
  image as a link to its storage URL with the display text, a code block as inline `Code`
  holding the whole listing, and a table as its display inlines. None of these is a usable
  "see figure 3".
- **The toolchain numbers unevenly** (verified against Pandoc 3.8.3 on 2026-10-17). Given a
  Pandoc `Figure` holding an image with a caption, a `Table` with a caption, and a `Figure`
  holding a code block:
  - the **Typst** writer emits `#figure(image(...), caption: [...])`, `#figure(table(...),
    caption: [...], kind: table)`, and `#figure([code], caption: [...])` with the element's
    identifier as a Typst label, and a link to the identifier as `#link(<label>)[...]`; Typst then
    numbers each kind in its own series (image, table, raw) and the Bergfink template already
    sets the supplements *Fig.*, *Table*, and *Listing* and the caption positions (above a
    table, below the others);
  - the **HTML** writer, which the EPUB uses, emits `<figure id>` with a `<figcaption>` and
    `<table id>` with a `<caption>`, unnumbered;
  - the **GFM** writer emits the same `<figure>` as raw HTML, and a table's caption as a stray
    paragraph after the table carrying the identifier in braces.
- **The template is ready for lists.** Bergfink has `lof`/`lot` variables and titles (*List of
  figures*, *List of tables*); Typst's `outline(target: figure.where(kind: image))` lists figures
  with page numbers. Nothing sets them.
- **Chicago's rules** (3.9, 3.50–3.54, 1.39–1.40): figures and tables are numbered in separate
  series; in a book with many, by chapter ("figure 2.3", *double numeration*), else straight
  through; the caption carries the capitalized label (*Figure 2.3*), a text reference the
  lowercase word (*see figure 2.3*); a figure's caption sits below it, a table's title above;
  a list of illustrations or tables is optional and belongs after the contents. Chicago has no
  rule for code listings; *Listing 2.1* is the common convention.


## Requirements

Proposed, not yet agreed. Requirements marked *(book)* come from the SCFH book.

- **R1 — No new authoring syntax for a reference.** An *aliased* block reference in the running
  text is the cross-reference: `[label](((uid)))`, as Roam makes it. Its alias is either a kind
  word, which Guffin completes with the number (`[figure](((uid)))` renders *figure 2.3*), or
  the author's own words, kept verbatim. A plain `((uid))` is not a reference an author would
  write inside a sentence: in Roam it transcludes the target, so the diagram, the table, or the
  listing itself would render in the middle of the prose. *(Amended 2026-10-17; see Q6.)*
- **R2 — Typed rendering.** A reference to a figure renders as its number with its kind's word
  (*figure 2.3*), linked to the figure, in every format that can link. *Accepted 2026-10-17.*
- **R3 — Three series.** Figures (images), tables, and listings (code blocks) are numbered in
  separate series. *Accepted 2026-10-17.*
- **R4 — One number, every format.** A figure has the same number in the PDF, the EPUB, and the
  Markdown, so a reader of one edition can talk to a reader of another. *Accepted 2026-10-17.*
- **R5 — Only the captioned are numbered.** *(book)* An illustration with no caption is chapter
  art: it gets no number, no label, and no entry in any list. A captioned image, table, or
  listing is a numbered float. *Accepted 2026-10-17.*
- **R6 — Chapter-scoped numbers in a book.** *(book)* A book numbers by chapter, *figure 2.3*; an
  article or manuscript numbers straight through, *figure 3*. The project type decides.
  *Accepted 2026-10-17.*
- **R7 — Lists.** A list of figures, and of tables, can be generated into an authored front-matter
  section, as the Notes section is generated into an authored `endnotes` section.
  *Accepted 2026-10-17.*
- **R8 — Validation.** A reference to a figure-like block that is never displayed in the document
  (so has no number), and a figure displayed twice, are reported. *Accepted 2026-10-17.*
- **R9 — Markdown degrades gracefully.** GFM cannot draw a figure; the number appears in the
  caption and references link to the figure, as heading links do today. *Accepted 2026-10-17.*


## Open questions

### Q1 — What makes a float

Which image, table, or code block gets a number?

- **(a) Every one.** Simple, wrong for chapter art, and it would number the one-line listings an
  explanation quotes in passing.
- **(b) The captioned ones.** Quarto's rule: a captioned image standing alone is a figure. An
  image's or listing's children are already its caption, so for those two kinds this needs no
  new syntax; a table needs a way to carry a caption (Q2). An uncaptioned diagram would then be
  unnumbered, which is Chicago's rule too: a figure without a caption cannot be referred to.
- **(c) A tag.** `figure:: true`, or a kind tag, on the block. Explicit but a chore, and it
  separates "is a figure" from "has a caption", which Chicago joins.

*Decided 2026-10-17, by Q2:* a float is a **wrapper block tagged `float::`** whose text is the
caption, so (b) and (c) are joined: the tag declares the float, and the caption comes with it,
since the tagged block's text is the caption. A bare image, table, or code block, however it is
nested, is never a float; the chapter art stays unnumbered without any opt-out. The earlier
refinement (a referenced bare block becomes a float) is dropped: a kind-word alias pointing at
anything but a wrapper is a validation error (Q10), and an author who wants to refer to a
picture wraps it.

### Q2 — Where a caption lives

*Decided 2026-10-17 (Joe): (e), the float is a wrapper block.* One mechanism for all three kinds,
and the caption an inherent property of the float rather than of any place it is shown.

**The float is a block of its own**, as a Pandoc `Figure` is a container holding content and a
caption:

- The wrapper block's **text is the caption**. The image, the table, or the code block **nests
  beneath it** as its child. A `guffin-meta::` child of the wrapper declares the kind:
  `float:: figure`, `float:: table`, or `float:: listing`.
- **The tag is what makes a caption a caption.** A line of text with a code block nested under it
  is the commonest structure in the graph (the lead-in and its listing), and none of those may
  become a numbered float by accident. The tag is also where the kind check lands: `float:: table`
  over an image is a validation error (Q10).
- **The wrapper's uid is the float's identity.** A reference points at the wrapper,
  `[figure](((wrapper-uid)))`, and never needs to know what is inside. Displaying the float
  elsewhere is an embed of the wrapper, `{{embed: ((wrapper-uid))}}`, which in Roam shows caption
  and content together; Guffin treats a standalone *reference* to a wrapper the same way, since a
  float is atomic and a caption without its content means nothing. Two embeds of one wrapper are
  the double display of Q5.
- **Nothing is added under a table**, whose children stay its rows; the caption sits above it in
  the outline, where Chicago puts a table's title. For an image or a listing the caption sits
  above in Roam and renders below in the output, a rendering matter.
- **Today's convention survives as the legend.** An image's or listing's own children keep
  rendering as caption-styled text beneath it (`_caption_blocks`). Inside a float that text is
  the *legend*, the longer explanation under the caption, Chicago's distinction; outside a float
  it is what it is today, styled text under an unnumbered picture.

The rejected options, kept for the record:

- **(a) Children as the caption for images and listings, a `caption::` attribute for tables.**
  Two mechanisms, and the table half fails: Joe tried it, and any attribute or metadata block
  nested under a `{{[[table]]}}` block appears in Roam as table content.
- **(b) A `caption::` attribute for all three.** Fails for tables for the same reason.
- **(c) The alias of the standalone reference that displays the float is its caption.**
  Semantically wrong, as Joe put it: it ascribes an inherent property of the thing by extracting
  it from a reference to the thing, and a table shown from two places would be captioned twice,
  possibly differently, and numbered twice.
- **(d) Text beside the marker in the table's own block**, `{{[[table]]}} Caption`. Untested, and
  not one mechanism: an image's block is its link, a code block's is its fence.

### Q3 — The numbering scheme

*Settled by R3 and R6 (accepted 2026-10-17), except the last point, deferred.*

- Three series: figures, tables, listings. Per Chicago and R3.
- A book numbers by chapter: the chapter number, a period, the ordinal within the chapter
  (*2.3*); numbering restarts at each chapter. Chicago's double numeration. An article or
  manuscript numbers straight through. Per R6, carried on `StructuralPolicy` as a
  `float_numbering` directive beside `note_style`.
- In a parts book the part number is not part of the figure number (Chicago).
- **Deferred (Joe, 2026-10-17):** a float in the front or back matter (an appendix's table). The
  options noted for when it comes up: the appendix letter as the chapter number (`A.1`), or a
  short series of its own per element. Until then a front- or back-matter float is numbered as
  if its element were a chapter, which is wrong but visible, and the book has none.

### Q4 — Who numbers

- **(a) Typst numbers the PDF; Guffin numbers the EPUB and Markdown.** Typst's figure counters
  give chapter-scoped numbers with a show rule. Two numberings that must agree is the hazard:
  Typst counts every `#figure`, Guffin would have to predict exactly that set.
- **(b) Guffin numbers everything.** One pass over the built document assigns each float its
  number in reading order, chapter-scoped per Q3, and writes the label into the caption as text
  (*Figure 2.3.*). The PDF turns Typst's own figure numbering off (`figure(numbering: none)`),
  keeping `#figure` for its placement, captions, and outlines. The number is then identical in
  every format by construction, as the Notes section's entries are.

*Decided 2026-10-17 (Joe): (b).* Guffin numbers everything. The pass is the twin of
`placed_note_citations`: walk the render-visible document in reading order, embeds descending
at their site, counting floats per kind and resetting at each chapter heading.

### Q5 — Display sites and homes

*Decided 2026-10-17 (Joe): first display wins.*

A float's home may be a collection page, displayed in a chapter by an embed or a standalone
reference of its wrapper (Q2), as the SCFH epigraphs are. The number belongs to the **display
site**: where the float appears in reading order, not where it lives. A float displayed twice
would get two numbers, so **the first display numbers it**; a later display is a validation
warning (R8) and renders the float again, unnumbered, with its caption. A reference from the
text resolves to the number of the display, so a reference to a float never displayed has no
number: a validation error, rendered as the display text unlinked.

### Q6 — Rendering a reference

*Decided 2026-10-17 (Joe):* the aliased reference is the cross-reference, and its alias decides
what renders.

An **inline** reference (amid text) to a float renders, linked to the float, as:

- **a kind word, completed.** An alias that is exactly the kind's word, *figure*, *table*, or
  *listing*, renders as that word followed by the number: `[figure](((uid)))` renders
  *figure 2.3*. The match is on the whole alias, case-insensitively, and the alias's own case is
  kept, so `[Figure](((uid)))` opening a sentence renders *Figure 2.3*; Chicago's lowercase in
  running text is then the author's to write, as it should be. The three words are the kinds'
  labels, carried by `FloatKind` and used by the captions and the generated lists too, so the
  author meets one vocabulary everywhere; the list is closed, with no synonyms (*diagram*,
  *illustration*) and no abbreviation (*fig.*), which Chicago does not use in running text
  either. **The word must name the target's kind**: `[table](((uid)))` pointing at an image is a
  validation error (Q10), not a silent correction, since the sentence promised a table.
- **any other alias, verbatim.** `[the diagram above](((uid)))` renders those words. A label that
  is itself a number is the author's to write and to keep current.
- **a plain `((uid))`**, which no one should author inside a sentence (R1), renders as the
  completed lowercase label all the same, so it is never an error.

A **standalone** reference keeps today's meaning: it displays the float. Nothing changes there.

A reference to two floats, *figures 2.3 and 2.4*, has no completed spelling; the author writes
*figure 2.3 and figure 2.4* as two references, or an explicit alias.

### Q7 — The Pandoc model

*Decided 2026-10-17 (Joe).* In Guffin's model the three kinds are one thing, a wrapper with a
kind, a caption, and content (Q2); only the last step, encoding the float into Pandoc's AST,
branches, because Pandoc's `Table` carries a `Caption` of its own while an image or a code block
has no caption slot:

- An image float becomes a Pandoc `Figure` holding the image (with its legend, Q2), its
  `Caption` the wrapper's text led by the number, its identifier `float-<wrapper-uid>` (the
  heading-anchor convention, `vertex-<uid>`, is for headings; a float is a different namespace
  so that a reference to a float and to a heading can never collide).
- A listing becomes a `Figure` holding the `CodeBlock` (with its legend); Typst infers
  `kind: raw` and the template's listing rules apply; the `code-source` attribution stays below
  the listing, inside the figure's blocks.
- A table float gets its `Caption` on the `Table` itself, with the same identifier. Wrapping the
  table in a `Figure` instead was tested (Pandoc 3.8.3, 2026-10-17): the Typst writer nests a
  captioned, label-bearing outer figure around an inner `kind: table` figure with no caption,
  so Typst would count the outer in the image series and the template's table rules would hit
  the captionless inner one; the GFM writer gives up the pipe table for a raw HTML `<table>`;
  only the HTML writer is indifferent. (ChatGPT reports the same disagreement in writers Guffin
  does not use: Pandoc 3.12's LaTeX writer drops the outer figure, caption and label with it,
  and the Docx writer adds a layout table.) The caption on the `Table` avoids the question in
  every writer.
- The `caption` Div and the three `*_caption.lua` filters stay for the legend; an uncaptioned
  image or listing (not a float) keeps today's rendering untouched.

### Q8 — Per format

*Decided 2026-10-17 (Joe).* Only Markdown had a real choice.

- **PDF.** `#figure` from Pandoc, with a `set figure(numbering: none)` rule so the label Guffin
  wrote into the caption (*Figure 2.3.*) is the only number, and the supplement suppressed with
  it; the template's caption positions already match Chicago. The alternative, Typst numbering,
  is what Q4 rejected. Lists via Typst outlines when the author's list section is present (Q9).
- **EPUB.** The HTML writer's `<figure id>`/`<figcaption>` and `<table id>`/`<caption>`, the right
  elements and ones every reading system in use styles, dressed by `epub.css` to the design
  language's caption treatment; references are `<a href="#float-<uid>">`, which Pandoc rewrites
  across content documents. A `div` scaffold would only matter for a reader that mishandled
  `<figure>`, and none does.
- **Markdown: unwrap to Markdown, as today.** An image paragraph, or a fenced code block, with
  the caption as an italic line beneath led by the label, which is what `gfm_caption.lua`
  produces now plus the label; an empty `<a id="float-<uid>"></a>` anchor above it carries the
  identifier, the device heading links already use. A table float's caption is placed *above*
  the table, as Chicago has it, by Guffin rather than by the writer, whose own output is a stray
  paragraph after the table with the identifier in braces. Rejected: the GFM writer's raw-HTML
  `<figure>` (an HTML island in a Markdown file, and a listing inside it is highlighted
  `<span>` soup rather than a fenced code block, a real loss in a `.md`), and a mix of the two.
  The Markdown export is read in Typora and on GitHub, and R9 already concedes it degrades;
  a fenced listing under a labelled caption line is the graceful degradation.

### Q9 — The lists

*Decided 2026-10-17 (Joe).*

A list of figures or tables is generated, like the Notes section, into an **authored** heading
tagged `element-type:: list-of-illustrations` (figures) or a new `list-of-tables` (tables), so
the author decides whether the book has one and where it sits. Listings get no list: Chicago has
none, and the practice of technical publishers (Manning, O'Reilly, the classic CS books) is to
number and caption listings in the text without a front-matter list, which only LaTeX-set
books tend to carry because `\lstlistoflistings` is free. A map from the book's listings into
the companion repo is a useful thing of a different kind, a back-matter section written by
hand, outside this design.

- **PDF:** a Typst outline of the kind's figures, with page numbers.
- **EPUB and Markdown:** a generated list of links, number and caption, one per float, in
  reading order.
- Without the heading, no list: Guffin fills an authored section and never invents one. With
  the heading and no floats of the kind, the section is dropped from the output rather than
  rendered empty, with a warning so the author knows the heading does nothing. (Weaker than the
  notes rule, which aborts a `book` that cites notes without an `endnotes` heading, because a
  missing list loses no content.)

### Q10 — Validation

*Decided 2026-10-17 (Joe).* Seven new `publishing_validation` rules over the render-visible
document, six fatal and one advisory:

1. **A float's caption is empty** — a wrapper whose text is blank. Fatal.
2. **A `float::` value is not a kind** — not `figure`, `table`, or `listing`. Fatal (the
   `all_*_values_legal` pattern).
3. **A wrapper's content does not match its kind** — `float:: table` over an image, or the
   wrapper has no content child, or more than one. Fatal.
4. **A kind-word alias names a kind other than its target's** — `[table](((uid)))` on a figure
   wrapper, or a kind-word alias pointing at anything but a wrapper (Q1, Q6). Fatal.
5. **An inline reference to a float never displayed** — the float has no number to resolve to
   (Q5). Fatal.
6. **A float displayed more than once** (Q5). Fatal.
7. **A `list-of-illustrations` or `list-of-tables` heading with nothing to list** (Q9). A
   warning; the section is dropped.

The fatal rules abort an export with exit 1 and are advisory warnings in `dump-roam-tree`, as
every `validate_semantics` rule is. Rules 5 and 6 need the display walk (reading order, embeds
descending at their site), so they sit with the note rules that need `placed_note_citations`
rather than with the per-vertex tag checks; rule 7 is a renderer-time warning, not a validator.


## Implementation sketch

1. **Vocabulary** *(built 2026-10-17)*. `StructuralElement.LIST_OF_TABLES` (`list-of-tables`, front matter, EPUB
   `lot`). A `FloatKind` StrEnum (`figure`/`table`/`listing`), each member carrying its label
   word (the caption's capitalized label, the reference's completed word, the list's name) and
   the vertex type it wraps, in `model/` beside the vocabulary. `PublishingSemantics.FLOAT`
   (`float:: <kind>`, anchored to the text block that is the wrapper), read by `float_of()` /
   `float_of_vertex()` like the other tags.
2. **Model** *(built 2026-10-17; `model/floats.py`)*. `model/floats.py`: `float_wrapper(vertex, tree)` (the wrapper's kind, caption text,
   and the wrapped content vertex — the child whose type the kind names), `placed_floats(tree)`
   in reading order with each float's governing chapter heading (the `placed_note_citations`
   walk, generalized, descending embeds at their site), and `float_numbers(tree, policy)`
   assigning `FloatNumber(kind, chapter, ordinal)` per display site.
3. **Policy** *(built 2026-10-17)*. `StructuralPolicy.float_numbering`: `by-chapter` for book, `sequential` for
   article and manuscript.
4. **Render** *(built 2026-10-17; `floats_rendering.py`, `gfm_float.lua`)*. `pandoc_rendering`: a wrapper renders as a `Figure` whose `Caption` is the
   wrapper's text led by the number (*Figure 2.3.*) and whose blocks are the wrapped content
   rendered as today (an image with its legend, a code block with its legend and attribution, a
   table), with the identifier `float-<wrapper-uid>`; a table float's `Caption` goes on the
   `Table` itself when a format does better with it there. A standalone reference or an embed
   of a wrapper renders the whole float. `make_resolver` renders an inline reference to a
   wrapper as the linked label (Q6). The Typst template: `#show figure: set figure(numbering:
   none)`. EPUB CSS for `figure`/`figcaption`/`caption`. Markdown: the unwrapped form of Q8, with `<a id>` anchors as for
   headings.
5. **Lists** *(built 2026-10-18)*. `render/floats_rendering.py`: `insert_float_lists()`, run after link
   resolution (so each caption is copied labelled and resolved, its links flattened) rather than
   beside `insert_notes_section()`.
6. **Validation** *(the six fatal rules built 2026-10-17)*. The seven rules of Q10: the per-vertex ones in `publishing_validation`, the
   two display-walk ones beside the note rules that need the walk, the list warning in the
   renderer.
7. **Fixtures.** A figure, a table, and a listing float (wrapper, tag, content), and references to
   each on a Test Article; regenerated baselines.


## Decisions

- **2026-10-18 — The lists, as built.** The PDF list is a Typst outline targeting the listed
  floats' own labels (`selector(<float-a>).or(…)`), not `figure.where(kind: …)`: Pandoc writes
  every table as a `kind: table` figure, captioned or not, so a kind outline would list the
  uncaptioned non-float tables too. The EPUB and Markdown lists are links whose text is the
  float's labelled caption. Building the EPUB list showed that Pandoc 3.8.3 resolves a link
  across its split content documents for a Div's, Span's, or Table's identifier but not a
  Figure's, so the EPUB renderer moves each float Figure's identifier onto a wrapping Div; this
  also mends running-text references to a figure or listing in another chapter. An authored
  list heading with nothing to list is removed with its section and a warning (rule 7).
- **2026-10-18 — Every chapter counts toward a float's chapter number.** Test Article 7's table,
  in the book's thirtieth chapter, came out as Table 5.1: `model/floats.float_numbers` gave a
  chapter its ordinal only when a float was met in it, so it counted the chapters holding
  floats. It now counts every body-matter heading at the chapter level in reading order, as the
  rule above states. In a parts book that count runs through the parts (Chicago's consecutive
  chapter numbering), while the numbered PDF and EPUB exports labelled a chapter by part and
  chapter (Book II's thirteenth chapter was *2.13*), so the table's number and its chapter's
  heading number disagreed.
- **2026-10-18 — A parts book follows the Chicago convention for its heading numbers too (Joe).**
  Chapters are numbered consecutively through the whole book, parts on their own in roman
  numerals, sections under their chapter (*30.1*), so heading and float numbers agree: Table 30.1
  sits in chapter 30. The writers cannot count that way, so Guffin numbers a parts book's
  headings itself (`render/heading_numbering.py`): PDF headings get a constant Typst numbering
  (`typst_heading_number.lua`), EPUB headings a leading `header-section-number` span in place of
  Pandoc's `--number-sections`. A book without parts keeps the writers' numbering, which already
  counts chapters straight through.
- **2026-10-17 — A labelled inline reference is not a standalone one.** Test Article 3's
  reference lines open with a coloured label span, so `[label]{color=...} see [figure](...)`
  begins with a bracket and ends with a vertex link, and
  `model/vertex_link.parse_standalone_vertex_link` took the whole text for the link: every
  float was counted as displayed twice and the export aborted. The parser now also requires
  the text's opening bracket to stay open until the link's own `](`; a backslash-escaped
  bracket counts for nothing.
- **2026-10-17 — The aliased reference needed its own transcription.** Until the first live
  reference was authored, `[figure](((uid)))` reached the model as a nested link: the
  `((uid))` inside the alias's URL slot was itself converted to a vertex link, so no vertex
  link existed for the model to see, validation had nothing to judge, and every format
  rendered the bare word. `transcribe/roam_md_to_pandoc_md.convert_block_link_aliases` now
  turns the alias into `[display](x-guffin:vertex/<uid>)` between the footnote-marker and
  block-link passes (`roam/markdown.BLOCK_LINK_ALIAS_RE`), keeping the author's display.
- **2026-10-17 — The aliased reference is the cross-reference (R1, Q6).** Joe pointed out that
  a plain `((uid))` inside a sentence transcludes the figure into the prose in Roam, so the
  author's page would be unreadable; the design had optimized the output and ignored authoring.
  The reference is therefore `[alias](((uid)))`. An alias that is exactly a kind word (*figure*,
  *table*, *listing*; closed list, case kept, must match the target's kind) is completed with the
  number; any other alias is the author's, verbatim. A kind-word alias naming the wrong kind is
  a validation error (Q10).
- **2026-10-17 — R2 accepted (Joe).** A reference renders as the kind's word and the number,
  linked, in every format that can link.
- **2026-10-17 — R3 accepted (Joe).** Figures, tables, and listings are numbered in three
  separate series.
- **2026-10-17 — R4 accepted (Joe).** A float has the same number in every format.
- **2026-10-17 — R5 accepted (Joe).** Only the captioned are numbered; uncaptioned chapter art
  gets no number, label, or list entry.
- **2026-10-17 — R6 accepted (Joe).** A book numbers by chapter, an article or manuscript
  straight through; the project type decides.
- **2026-10-17 — R7, R8, R9 accepted (Joe).** Lists generated into authored sections; undisplayed
  references and double displays reported; Markdown carries the number in the caption and links
  as heading links do. Every requirement is now accepted, R1 in its amended form.
- **2026-10-17 — Q2: the float is a wrapper block (Joe).** One mechanism for all three kinds: a
  block whose text is the caption, whose `guffin-meta::` child declares `float:: figure|table|
  listing`, and whose child is the image, table, or code block. The wrapper's uid is the float's
  identity for references and embeds. Joe rejected captioning through a reference's alias as
  semantically wrong (a property of the thing extracted from a reference to it; two references
  would caption it twice), and metadata under a table as impossible (Roam shows it as a row).
- **2026-10-17 — Q3 settled by R3 and R6; front- and back-matter floats deferred (Joe).** Rare
  enough to wait; the options stay noted in Q3.
- **2026-10-17 — Q4: Guffin numbers every format (Joe).** One reading-order pass assigns each
  float its number and writes the label into the caption; the PDF turns Typst's own figure
  numbering off and keeps `#figure` for placement, captions, and outlines.
- **2026-10-17 — Q5: first display wins (Joe).** The number belongs to the display site in
  reading order; a second display is a warning and renders unnumbered; a reference to a float
  never displayed is an error.
- **2026-10-17 — Q7: `Figure` for image and listing floats, the `Table`'s own `Caption` for a
  table float (Joe).** A table inside a `Figure` was tested and rejected: Typst nests two
  figures and counts the wrong one, GFM loses the pipe table.
- **2026-10-17 — Q8 (Joe).** PDF: Pandoc's `#figure` with Typst numbering and supplement off.
  EPUB: the writer's `<figure>`/`<figcaption>` and `<table>`/`<caption>`, styled by `epub.css`.
  Markdown: unwrapped to an image paragraph or fenced code block with a labelled italic caption
  line and an `<a id>` anchor, the table caption placed above the table; the GFM writer's raw
  `<figure>` rejected.
- **2026-10-17 — Q9 (Joe).** Lists of figures and tables generated into authored
  `list-of-illustrations` / `list-of-tables` headings; no list of listings; an authored heading
  with nothing to list is dropped with a warning.
- **2026-10-17 — Q10 (Joe).** Seven validation rules: empty caption, illegal kind value,
  content not matching the kind (or missing, or more than one), kind-word alias mismatch,
  reference to an undisplayed float, double display, all fatal; an empty list section a warning.
  **Every question is now decided except the deferred corner of Q3; the design is ready to
  build.**
