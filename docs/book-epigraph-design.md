# The book epigraph: an epigraph page before the contents

**Status: designed and built** (designed 2026-10-15, built 2026-10-16 per the proposals under
each open question, which Joe accepted as written; see [Decisions](#decisions)). This is the
working design document for the *book epigraph*: an epigraph that belongs to the whole work rather
than to a chapter, and the page it gets in a `book` export. The implementation follows the
[sketch](#implementation-sketch) below; the one departure is noted there.

Companion docs: [chicago-front-matter.md](chicago-front-matter.md) (Chicago's rules for the
front matter and the epigraph, which this design applies), [notes-design.md](notes-design.md)
(the shape this document follows), [publishing-semantics.md](publishing-semantics.md) (the
`element-type::` vocabulary, whose front-matter members this touches),
[render-pipeline.md](render-pipeline.md) (where the lifting described here runs). The layout of an epigraph itself (flush left under its heading, the source
line flush right within the epigraph's own box, the EPUB variant) was decided on 2026-10-12 and is
recorded in the SCFH project's `CLAUDE.md`; this document leaves that layout alone.


## Why

Chicago (17th ed., 1.4 and 1.36) places a book's epigraph in the front matter *before* the
contents: on the page after the dedication, or after the copyright page when there is no
dedication. Its one alternative position is the verso of a second half title, facing the first
page of the text. A position after the contents is neither.

Guffin's `book` layout today sets the title page, then the table of contents, then the document,
and an epigraph authored above the export root's first heading is the document's first block. So
in the PDF the book epigraph lands on the first page after the contents. In the EPUB the order
happens to be right, because the spine carries no contents page (reading systems show the nav
document instead), but the epigraph's document is wrong in three ways: Pandoc gives leading content
without a heading the book's title as its heading, the document is classed `bodymatter`, and it
appears in the navigation as an entry titled with the book's name.

The case that prompted this: `[[draft-2]]` now carries the book's epigraph as its second block, a
block reference to a Perlis epigraph kept on the `[[Epigrams]]` page, and the export of
2026-10-15 set it on page 3, after the contents.


## Current state (as of `2a78d69` plus the uncommitted preamble fix)

- **Model.** `is_epigraph` (`model/vertex.py`) recognizes a `QuoteBlockVertex` of
  `QuoteType.EPIGRAPH`. `drop_root_preamble` (`model/vertex_tree.py`) prunes the export root's
  children ahead of its first heading but keeps an epigraph among them, and, since today, a child
  that is a standalone vertex link to an epigraph (`standalone_link_target`), since a page's
  epigraph is usually a block reference to one kept on a collection page. Only a `book` export
  prunes (`StructuralPolicy.drop_preamble`).
- **Rendering.** `pandoc_rendering` renders an epigraph as a `Div.epigraph` holding
  `Div.epigraph-text` and, when attributed, `Div.epigraph-attribution`, stamped
  `epub:type="epigraph"`. A standalone block reference renders as the referenced block, so a
  reference to an epigraph yields the same `Div`. `typst_quote.lua` turns the `Div` into a call to
  the template's `#epigraph(quote:, attribution:)` helper (`default_styles.typ`); `epub.css`
  styles `div.epigraph`; `gfm_quote.lua` renders it as a block quotation.
- **PDF layout.** `bergfink.typst` emits, in order: the cover page when `cover-image` is set, the
  title page when `titlepage` is set (`titlepage.typ`), the abstract and thanks when either is set
  (`abstract.typ`), the outline when `toc` is set (`toc.typ`, with `cfg.toc-own-page` and roman
  `cfg.toc-page-numbering`), then the page setup for the body and `$body$`. The abstract reaches the
  template as a metadata value rendered to Typst (`#(cfg.abstract = [$abstract/nowrap$])`), which
  is the pattern the epigraph page can follow.
- **EPUB layout.** Pandoc splits the document at the split level (`--split-level`, 2 in a parts
  book). Leading content ahead of the first split-level heading becomes the first content document
  after the title page, under a heading Pandoc makes from the document title, with its body typed
  `bodymatter`, and listed in the nav and the NCX. `epub_post_processing` already rewrites the
  packaged e-book in place (`restore_matter_divisions`, the title-page stamps, `append_colophon`,
  `bake_code_line_numbers`), so a further pass has somewhere to live.
- **Markdown.** No contents page; the epigraph is the first block after the title. Nothing to fix.


## Requirements

- **R1 — Chicago's position.** In a `book` export the leading epigraph gets a page of its own in
  the front matter, after the copyright page and the dedication, whichever the book has, and before
  the contents (see [chicago-front-matter.md](chicago-front-matter.md)). In the PDF that is a page
  of its own; in the EPUB a content document of its own, typed `frontmatter` with
  `epub:type="epigraph"`, with no heading and no entry in the nav or the NCX. Today Guffin sets
  neither a copyright page nor a dedication ahead of the contents (Q6), so for now the rule reduces
  to: directly after the title page, before the contents. The lifting and the page must not assume
  that reduction, so that the front-matter ordering of Q6 can later place those elements ahead of
  the epigraph without changing it.
- **R2 — The epigraph's own layout is unchanged.** The page uses the same `#epigraph` helper and
  the same EPUB styles as a chapter epigraph: flush left, the box as wide as its longest line, the
  source flush right within it. Only the page around it is new.
- **R3 — Only the book's epigraph moves.** The rule applies to epigraphs ahead of the export root's
  first heading, in a profile whose policy asks for it (the `book` profile). A chapter's epigraph,
  under its chapter heading, stays where it is. An `article` or `manuscript` export, which has no
  title page or contents, keeps a leading epigraph in the flow as today.
- **R4 — Several epigraphs share the page.** Chicago allows more than one; all leading epigraphs
  are set on the one page, in order.
- **R5 — A block reference counts as the epigraph.** Already true for the prune and for rendering;
  the lifting must see the resolved `Div`, not the reference.
- **R6 — Nothing new to author.** Placement follows from position and type: an epigraph above the
  root's first heading. No tag.
- **R7 — Other exports are unaffected.** Markdown is unchanged. A `notes_only` export, which cuts
  the document down to the Notes section, renders no epigraph page. `--no-preamble` still drops
  the loose preamble around the epigraph, which is kept as today.


## Open questions

### Q1 — The epigraph page

What the PDF page looks like: whether it carries the running head and page footer (the title page
carries neither), whether it counts in the front matter's roman numbering while showing no number
(as the title page does), and where on the page the epigraph sits. Printed books set an epigraph
page's text a third or so down from the top, at the text block's left margin.

*Proposal:* no header or footer, no printed number, the epigraph set at the body text's left
margin with a sink of about a third of the page height (`cfg.epigraph-page-sink`, a ratio of the
page height, 0.3 by default), and the page ends with a page break so the contents open on a fresh
page. In the EPUB, the document is the epigraph alone; a top margin of a few ems stands in for the
sink, since reading systems control the page.

### Q2 — More than one epigraph

*Proposal:* all leading epigraphs on the one page, each set by the helper, with the helper's own
spacing between them. No limit.

### Q3 — The EPUB navigation

Whether the epigraph document appears in the nav at all. Chicago's contents never list an
epigraph, and reading systems show the nav as their contents.

*Proposal:* omit it from the nav and the NCX. The document stays in the spine, linear, so readers
paging from the title page meet it.

### Q4 — The EPUB mechanism

Two ways to get the document right. (a) *Post-process Pandoc's chunk:* let Pandoc isolate the
leading epigraph into the first content document, then rewrite that document (drop the heading
Pandoc added, type the body `frontmatter` and the section `epigraph`) and remove its nav and NCX
entries. (b) *Build the document:* lift the epigraph before Pandoc runs and inject a hand-built
document into the package, editing the manifest, spine, nav, and NCX.

*Proposal:* (a), marked rather than inferred. The renderer wraps the lifted blocks in a `Div`
carrying a marker class (`book-epigraph`) before the Pandoc build, so the post-processing pass
finds the document by the class rather than by its shape. `restore_matter_divisions` must leave
the result alone or agree with it (`frontmatter`).

### Q5 — The PDF mechanism

The template must set the epigraph between the title page and the outline, which the body cannot
reach. (a) *Metadata:* lift the `Div`s out of the document and pass them to Pandoc as a metadata
value, which Pandoc renders to Typst for the template variable, as the abstract is passed
(`#(cfg.book-epigraph = [$book-epigraph/nowrap$])`); a new partial, `epigraph.typ`, sets the page
when the value is present. (b) *Strings:* pass the quotation and attribution as plain variables and
let the partial call `#epigraph(quote:, attribution:)` itself, at the cost of flattening any inline
markup in the quotation.

*Proposal:* (a). Its one risk: the metadata value must come through `typst_quote.lua` so that the
`Div` becomes the `#epigraph(...)` call; Pandoc applies Lua filters to metadata blocks, but the
first implementation step is to confirm it. If it does not, build the call in Python from the
`Div`'s parts.

### Q6 — The rest of the front matter (out of scope here)

Chicago's order runs half title, title, copyright, dedication, epigraph, contents, then lists,
foreword, preface, and acknowledgments. Guffin sets every authored front-matter section
(`element-type:: copyright-page`, `preface`, and so on) after the contents, as a division of the
document. An authored copyright page or dedication therefore follows the epigraph page and the
contents, which Chicago would reverse. This document does not take that on; the epigraph page is
designed so a later front-matter ordering can move those sections ahead of it without changing it.

### Q7 — The policy directive

Where the behavior is switched on. *Proposal:* a new `StructuralPolicy` directive,
`epigraph_page: bool`, `True` for `BookProfile` and `False` for the article and manuscript
profiles, beside `emit_title_page` and `emit_toc`, rather than deriving it from those two.


## Implementation sketch

Per layer, assuming the proposals above:

- **Policy** (`render/project.py`): `StructuralPolicy.epigraph_page`.
- **Lifting** (a small function beside `insert_notes_section` in the render layer, after link
  resolution so references are resolved): take the run of `Div.epigraph` blocks at the head of the
  document, ahead of its first `Header`, and return them with the rest of the document. Nothing is
  lifted when the policy is off, when `notes_only` is set, or when the head of the document is not
  an epigraph.
- **PDF** (`render/pdf_rendering.py`, `typst_resources/`): pass the lifted blocks as the
  `book-epigraph` metadata value; `bergfink.typst` gains `#(cfg.book-epigraph = …)` and emits
  `$epigraph.typ()$` after `titlepage.typ` and before `abstract.typ`/`toc.typ`; `epigraph.typ`
  sets the page per Q1; `base_cfg.typ` gains `book-epigraph: none` and `epigraph-page-sink`.
- **EPUB** (`render/epub_rendering.py`, `render/epub_post_processing.py`): wrap the lifted blocks
  in `Div.book-epigraph` and put them back at the head of the document for Pandoc to chunk; a new
  pass, `set_epigraph_document`, finds the content document holding `div.book-epigraph`, removes
  the heading Pandoc inserted and the section's title id, types the body `frontmatter` and the
  section `epigraph`, gives it a top margin (`epub.css`), and removes its nav and NCX entries;
  ordered before `restore_matter_divisions`, or that pass taught to leave it alone.
- **Markdown**: no change.
- **Tests**: the lifting function (policy on and off, reference-resolved epigraph, several
  epigraphs, `notes_only`); PDF page order (the epigraph page before the contents, its text absent
  from the body) via `pypdf`; EPUB spine order, `frontmatter` body, `epigraph` section, no nav or
  NCX entry; the existing chapter-epigraph tests unchanged.
- **Docs**: Guffin's `CLAUDE.md` (`project.py`, `pdf_rendering.py`, `epub_rendering.py`,
  `epub_post_processing.py`, the template partials); the SCFH project's `CLAUDE.md` epigraph
  bullets, which now say where the book epigraph lands.


## Decisions

- **The book epigraph goes before the contents, per Chicago** (Joe, 2026-10-15), asked for after
  the export of that day set it after them.
- **Built per the proposals** (Joe, 2026-10-16): Q1 the page as proposed (no header, footer, or
  printed number; a sink of 0.3 of the page height, `cfg.epigraph-page-sink`; a break after); Q2
  every leading epigraph on the one page; Q3 the EPUB document left out of the nav and the NCX; Q4
  Pandoc's own chunk finished by post-processing, found by the `book-epigraph` class; Q5 the
  metadata route, confirmed to carry the `#epigraph` call (Pandoc applies the Lua filters to
  metadata blocks); Q7 the `epigraph_page` directive. Q6, the ordering of authored front-matter
  sections, stays open. One departure from the sketch: the template takes the `book-epigraph`
  value up next to the partial's emission rather than with the other variables at the top, because
  a Typst content block evaluates where it is written and the value calls the `#epigraph` helper
  that `default_styles.typ` defines further down.
