# The `PublishingSemantics` vocabulary (model → format mapping)

This is a companion to [render-pipeline.md](render-pipeline.md), which covers the render layer's
four-phase pipeline and the project-type model. This doc goes deep on the format-independent
`PublishingSemantics` vocabulary and how each output format maps it.

`model/publishing_semantics.py` defines a **format-independent vocabulary aligned with publishing-industry
standards and conventions** — the semantic identity of the pieces of a document, independent of how
any output format renders them. It is intentionally *not* modeled on EPUB (or PDF, or GFM). The
book-anatomy taxonomy the tags take their values from — `Matter` and `StructuralElement`, whose
placements are the Chicago Manual of Style's rulings — lives in `model/chicago_structure.py`, a
pure taxonomy with no other `guffin` dependencies.

## The pieces

- **`PublishingAttribute`** — an `Attribute` pinned to the `guffin` domain, carrying an **`AttributeAnchor`**: the
  kind of vertex it attaches to, and where in the tree. The anchoring affordances themselves live
  in `model/attribute_anchor.py` — what the model *can express* is independent of how this vocabulary uses
  it. `AttributeAnchor` has `PAGE`, `HEADING`, `PDF`, `CODE_BLOCK`,
  `BLOCK`, `ANY`, and `ROOT`; each member carries two constraint axes a host vertex must satisfy:
  the `frozenset[VertexType]` it corresponds to (the AttributeAnchor↔VertexType correspondence is a single
  source of truth on the enum; `VertexType` is defined in `model/vertex.py`) and its `TreePosition`
  (`anywhere`/`root`). `BLOCK` covers every vertex type except a page and `ANY`/`ROOT` cover them
  all, derived from `VertexType` itself; `ROOT` is the positional anchor — type-independent, but
  its host must be the tree's root vertex (the export target: a page for a page export, a heading
  or block for a subtree export).
- **`PublishingSemantics`** — the enum of recognized guffin attributes, each a `PublishingAttribute`:
  - *Root-anchored document metadata* (`AttributeAnchor.ROOT`): `TITLE`, `SUBTITLE`, `AUTHORS`,
    `ILLUSTRATORS`, `DATE`, `PUBLISHER`, `RIGHTS`, `IDENTIFIER`, `LANGUAGE`, `DESCRIPTION`,
    `REVISION`, `COVER_IMAGE` — bibliographic facts about the work as a whole, folded
    from a `guffin-meta::` block on the export root (a referenced page's metadata can no longer
    masquerade as the work's own). `COVER_IMAGE` (`cover-image::`) is a Roam block reference
    `((<uid>))` to an image block — the cover is metadata rather than a `StructuralElement` because
    per CMOS only the book interior is matter-classified, the cover being exterior.
  - *Heading-anchored tags* (`AttributeAnchor.HEADING`): `ELEMENT_TYPE` (`element-type::`) declares which
    `StructuralElement` a heading is; `MATTER` (`matter::`) declares its `Matter` division directly,
    for a bespoke heading with no specific element type; `PAGE_BREAK` (`page-break::`) forces a
    `PageBreak` in paginated output (`before` opens the tagged heading on a new page). Whether the
    directive is *honored* is the project profile's decision, not the tag's: a book's pagination is
    fixed by its own structural conventions (chapters and parts open pages by ritual), so
    `BookProfile`'s policy sets `honor_page_breaks` off and every renderer drops the tags (with a
    warning per drop, via `drop_page_breaks()`), while the default and manuscript profiles honor
    them — content declares, policy disposes.
  - *PDF-anchored tags* (`AttributeAnchor.PDF`): `PDF_RENDER` (`pdf-render::`) declares an embedded PDF
    asset's `PdfRender` placement in paginated output (`inline` pages vs the default `link`).
  - *Code-block-anchored tags* (`AttributeAnchor.CODE_BLOCK`): `CODE_LANGUAGE` (`code-language::`)
    overrides the closed fence-language set the Roam UI offers, its value resolved against the
    canonical language vocabulary (`common/programming_language.py`); `CODE_SOURCE` (`code-source::`)
    records the GitHub provenance of a snapshotted listing — three ordered values (blob URL, commit
    SHA, fetch date) parsed to a `CodeSource`.
  - *Block-anchored tags* (`AttributeAnchor.BLOCK`): `PUBLISH` (`publish::`) declares a block's publication
    state; `publish:: false` omits the block and its entire subtree from every rendered output
    (untagged, `DEFAULT_PUBLISH` — published — applies).
- **`StructuralElement`** — the legal values of an `element-type` tag: a book's organizational parts
  (`TITLE_PAGE` … `COLOPHON`, incl. `PART`/`CHAPTER`/`SECTION`/`SUB_SECTION`/`SUB_SUB_SECTION`; no `cover`
  — per CMOS only the interior is matter-classified, the cover being exterior). Each member
  carries its **`Matter`** — the `front-matter`/`body-matter`/`back-matter` division it belongs to.
  This is the **conventional** placement, aligned with the **Chicago Manual of Style (CMOS)** and
  independent of any output format (e.g. `conclusion`/`epilogue` are body matter, `afterword` opens
  the back matter). How a given format's toolchain actually divides these parts is a separate concern,
  recorded per-format in `render/` (for EPUB, on `EpubType.division`; see below).

Member **names follow publishing labels** (`table-of-contents`, `list-of-illustrations`,
`about-the-author`), some of which deliberately diverge from any one format's terms — e.g. EPUB's
Structural Semantics Vocabulary abbreviates `table-of-contents`/`list-of-illustrations` to
`toc`/`loi`. That divergence is by design: the model speaks the publishing domain, and the render
layer translates. (Where a publishing label and a format term happen to coincide — `acknowledgments`,
`appendix`, `colophon` — no translation is needed; the member-keyed map still routes them explicitly.)

## Validation

`model/publishing_validation.py` is the vocabulary's **validation pass** — the counterpart to the
definitions in `model/publishing_semantics.py`. Definition and judgment are deliberately separate:
`publishing_semantics.py` says what the vocabulary *is*, while `publishing_validation.py` decides
whether a given document *uses it legally*. It judges a fetched `VertexTree` against the vocabulary
before any rendering happens, reporting every way the authored content breaks the rules (it
accumulates all violations rather than stopping at the first); its entry point is `validate_semantics()`.

The invariants it enforces fall into four groups:

- **Anchoring** — every recognized guffin attribute sits on a vertex its `AttributeAnchor` allows
  (document metadata only on the root, a heading tag only on a heading, and so on).
- **Value legality** — each tag's value is drawn from that tag's legal set: `element-type` names a
  `StructuralElement`, `matter` a `Matter`, `page-break` a `PageBreak`, `pdf-render` a `PdfRender`,
  `code-language` a canonical
  language, `code-source` a well-formed URL/commit-SHA/date triple, `publish` a boolean, `date` a
  W3CDTF reduced-precision date, and `cover-image` a block reference resolving to an image in the tree.
- **Placement** — a `matter` tag sits at the book's section level (level 1, or level 2 in a parts book).
- **Internal element numbering** — the author's bracketed element numbers (see
  `model/element_number.py`) are well-formed, appear on headings only, carry a legal matter segment
  that agrees with the heading's resolved matter, and are unique, in document order, and properly
  nested under any numbered ancestor.

Validation runs on every fetch (`cli/common.fetch_roam_trees`), but the consequence differs by
command: `dump-roam-tree` reports violations as advisory warnings — the dump always renders —
while `export-roam-tree` treats them as fatal, aborting the export with exit 1. A publishable
artifact must not be built from content that violates the vocabulary.

## How it maps to output (the design contract)

- Everything in `model/publishing_semantics.py` lives in `model/` with **zero render/format dependency**
  (it depends only on `model/` and `common/` — the structural primitives `attribute.py`, `vertex.py`,
  `vertex_tree.py`, the `attribute_anchor.py` affordances, the `chicago_structure.py` taxonomy, and
  the `code_source.py` / `element_number.py` value models — sitting near the top of that stack).
- Every per-format mapping lives in `render/`, as an **explicit map keyed on the model member** —
  never a name-equality lookup against the format's own vocabulary. Some members have no counterpart
  in a given format (and vice-versa), so the map is deliberately partial.
- **EPUB.** `render/epub_semantics.py::epub_type_for()` is the explicit `StructuralElement →
  EpubType` map (e.g. `COLOPHON → EpubType.COLOPHON`, `TABLE_OF_CONTENTS → EpubType.TOC`,
  `None` for elements with no EPUB term). During Doc construction, `pandoc_rendering._heading_semantics`
  uses a heading's `element-type` / `matter` tags to (a) stamp `epub:type` on the section header and
  (b) add the `unnumbered` class to any non-body-matter section, so only body-matter chapters are
  numbered — the class is stamped in the shared Doc build, so the exemption holds in **both**
  paginated formats (Pandoc's `--number-sections` for EPUB, the Typst writer for PDF), not just
  EPUB. A bare `matter::` tag **overrides** the element's default matter
  (logging any disagreement), letting an author place a bespoke or non-standard section. The
  `epub:type` rides along harmlessly in the other formats (GFM drops it, Typst ignores it).
  - **`EpubType.division` records Pandoc, not CMOS.** Whereas `StructuralElement.matter` is the CMOS
    placement (see above), each `EpubType.division` records the `<body epub:type>` division **Pandoc
    assigns that term out of the box** — verified empirically against Pandoc 3.8.3's output (Pandoc
    classifies only its own hardcoded subset and defaults the rest to `bodymatter`). The two are
    intentionally different reference points; their **divergence set** — currently `epigraph`,
    `introduction`, `table-of-contents`, `list-of-illustrations`, `prologue`, `afterword`, `glossary`,
    `endnotes` (flagged inline in `epub_semantics.py`) — is exactly what the `<body>` division
    post-processing (below) corrects. A characterization test (`test_epub_semantics.py`) re-derives
    `EpubType.division` from a live Pandoc run so any change in Pandoc's classification is caught.
  - **`<body>` division post-processing.** `pandoc_rendering._heading_semantics` stamps every
    matter-tagged heading with its CMOS division in a `data-guffin-matter` section attribute (mapped
    from `Matter` by `epub_semantics.epub_division_for_matter`); after Pandoc packages the EPUB,
    `render/epub_post_processing.py::restore_matter_divisions` rewrites each content document's `<body
    epub:type>` to that stamped division and strips the scaffold attribute. This is driven by the
    heading's **`Matter`**, not its `epub:type`, so it also corrects bespoke `matter::` sections that
    carry no `epub:type` (e.g. a matter-only "Who is this Book for?"). It is `<body>`-level metadata,
    invisible in Apple Books, but makes the package's structural semantics conformant.
- **PDF / GFM.** The tags drive two format-independent effects in PDF: the matter-derived
  `unnumbered` exemption (above) and, via `has_parts` → the PART division, part/chapter pagination.
  The **per-element** sibling map (`StructuralElement → PDF/Typst`, `→ GFM`) — the analogue of
  `epub_type_for`, letting an element's identity drive format-specific styling/placement — is not
  part of these formats; the `data-guffin-matter`/`epub:type` scaffolding rides along harmlessly
  (GFM drops it, Typst ignores it).
- **Authored page breaks (paginated formats).** A heading's `page-break:: before` tag is gated
  **upstream of the Doc build** by the profile's `honor_page_breaks` policy directive: a book's
  pagination is fixed by its own conventions, so every renderer applies
  `publishing_semantics.drop_page_breaks` (a warning per dropped tag) when the policy declines —
  the same drop-by-default shape as element numbers and code-source attributions, but decided by
  the *profile* rather than an option. When the tag survives, `pandoc_rendering._heading_semantics`
  stamps the `page-break-before` class on the Header in the shared Doc build, and each paginated
  format maps the class itself: `typst_page_break.lua` prepends a weak Typst `#pagebreak` (a heading
  already at a page top gains no blank page), and `epub.css` applies `break-before: page`
  (best-effort — reading-system support varies). GFM drops the class, having no pages.
- **Code-source attribution (all formats).** A `code-source::` tag (three ordered values:
  GitHub blob URL, snapshot commit SHA, fetch date) lands on `CodeBlockVertex.code_source` at
  transcription. The shared Doc build follows a sourced code block with a `code-source`-classed
  `Div` — one emphasized line linking the `github.com` blob page **pinned at the recorded SHA**
  (immutable even after the branch moves) plus the abbreviated SHA and fetch date — and each
  format styles the class itself, on the fancy-quote pattern: `typst_code_source.lua` (a
  caption-styled raw block), `gfm_code_source.lua` (unwraps to the bare italic line), and
  `epub.css` (`div.code-source`, no filter). Whether the attribution appears at all is decided
  **upstream of the Doc build**: attributions are authoring metadata, so every renderer clears
  the field via `model/vertex_tree.drop_code_sources` unless `RenderOptions.emit_code_sources`
  is set (the `--code-sources` flag) — the same drop-by-default shape as element numbers.
  Orthogonally, the export CLI verifies each sourced block against GitHub before rendering
  (`code_source_verification.py`, `--verify-code-sources`, default on): the URL's ref resolves
  to its tip commit via the GitHub API, the immutable SHA-pinned raw content is fetched and
  line-sliced, and any mismatch — `drift` vs `local-modification`, disambiguated by the recorded
  snapshot SHA — or fetch failure aborts the export with exit 1.
