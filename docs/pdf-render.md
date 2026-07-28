# `pdf-render`: how an embedded PDF is placed in each output format

The `pdf-render` tag (`model/publishing_semantics.PdfRender`) declares how a display occurrence of
an embedded PDF asset is placed in the exported document. This doc records, cell by cell, what each
member actually produces in each output format — both what the reader sees and whether the PDF file
itself travels with the output.

Companion to [publishing-semantics.md](publishing-semantics.md), which covers the vocabulary the tag
belongs to, and [render-pipeline.md](render-pipeline.md), which covers the phases these behaviours
are decided in.

The tag is declared on the `{{[[pdf]]: <url>}}` embed itself, or — because the pdf anchor sees
through standalone links — on a standalone block reference to it, in which case the reference site's
tag governs that reference and outranks the target embed's own tag. Placement therefore resolves
**per occurrence**: two references to the same PDF may place it differently.


## The vocabulary

Seven placements, spanning the whole space an author might ask for — deliberately including
combinations no format implements yet. Guffin applies no heuristic about what "makes sense": the
author states the intent, and a format that cannot honour it says so (see *Fallback*, below).

| member | where the pages go | at what fidelity | what stands at the embed |
|---|---|---|---|
| `INLINE_NATIVE` | at the embed | the format's own content | the pages themselves |
| `INLINE_IMAGE` | at the embed | page images | the pages themselves |
| `APPENDIX_NATIVE` | an appendix at the back | the format's own content | a link into the appendix |
| `APPENDIX_IMAGE` | an appendix at the back | page images | a link into the appendix |
| `INTERNAL_LINK` | — the file itself travels inside the output | — | a link to the contained copy |
| `EXTERNAL_LINK` | — the file stays where it is hosted | — | an ordinary URL link |
| `NAME_ONLY` | — nothing is reproduced or linked | — | the filename, as plain text |

Values are kebab-case: `pdf-render:: inline-native`, `pdf-render:: appendix-image`, and so on.


## What an untagged embed gets

There is no single default. What an untagged embed becomes depends on what is being produced — a
bundle can hand the reader the file itself, a lone `.md` can only point at where it is hosted, and
a book carries its referenced documents rather than pointing away from them. The matrix lives in
`render/pdf_placement.py`, not in the vocabulary, because it is a render-layer decision:

| | article | manuscript | book |
|---|---|---|---|
| `md --bundle` | `INTERNAL_LINK` | `INTERNAL_LINK` | `APPENDIX_NATIVE` |
| `md --no-bundle` | `EXTERNAL_LINK` | `EXTERNAL_LINK` | `EXTERNAL_LINK` |
| `pdf` | `APPENDIX_NATIVE` | `APPENDIX_NATIVE` | `APPENDIX_NATIVE` |
| `epub` | `APPENDIX_NATIVE` | `APPENDIX_NATIVE` | `APPENDIX_IMAGE` |


## What each format implements today

| placement | `md --bundle` | `md --no-bundle` | `pdf` | `epub` |
|---|---|---|---|---|
| `INLINE_NATIVE` | ✗ | ✗ | ✅ one full-width `#image(…, page: n)` per page, vector and searchable | ✗ |
| `INLINE_IMAGE` | ✗ | ✗ | ✗ | ✗ |
| `APPENDIX_NATIVE` | ✗ | ✗ | ✗ | ✗ |
| `APPENDIX_IMAGE` | ✗ | ✗ | ✗ | ✗ |
| `INTERNAL_LINK` | ✅ relative link to the copy in `.mdbundle/` | ✗ nothing to contain it | ✗ measured dead — see *Format capabilities* | ✗ untested — see *Format capabilities* |
| `EXTERNAL_LINK` | ✅ | ✅ | ✅ | ✅ |
| `NAME_ONLY` | ✅ | ✅ | ✅ | ✅ |

Everything marked ✗ falls back. Note the consequence of the two matrices together: **`pdf` and
`epub` exports warn on every PDF embed today**, because their default is `APPENDIX_NATIVE` and no
format implements it yet. That noise ends when the appendix placements are built.


## Fallback

An unsupported request lands on `NAME_ONLY` — `PDF_RENDER_FALLBACK` — and logs a warning naming the
placement, the format, and the PDF. Deliberately a single fixed member rather than a ranked chain:
a chain would have Guffin decide which *unasked-for* placement is closest to the request, and that
judgment belongs to the author.

The warning fires on every fallback, including when the request came from the default policy rather
than an authored tag. An unmet placement is worth knowing about either way.

Separately, an `EXTERNAL_LINK` whose asset URL ends `.enc` warns that the link points at
Roam-encrypted bytes and will not resolve outside the Roam client. The link is still rendered:
whether to point at the original is the author's call, and the warning only makes it an informed
one.


## Does the PDF file travel with the output?

Only `INTERNAL_LINK` carries the file, and only where the format can contain one. This is otherwise
a *packaging* question rather than a placement one — `--bundle` decides whether Markdown's assets
travel, and the other formats always carry their own.

| | `md --bundle` | `md --no-bundle` | `pdf` | `epub` |
|---|---|---|---|---|
| the PDF file travels | **yes**, under `INTERNAL_LINK` | no | no — fetched to a temp dir, read, discarded | no |


## Where each cell is decided

- **The shared build** renders every PDF occurrence as a `Para` holding one `Link`, labelled with
  the original upload filename when known (else the storage-key filename, Roam's `.enc` suffix
  stripped), pointing at the fetched local file when there is one and at the remote Cloud Firestore
  source otherwise. It stamps the link with the *authored* placement — or with
  `PDF_PLACEMENT_UNSET` when the occurrence carries no tag
  (`render/pandoc_rendering._pdf_vertex_to_blocks`).
- **The build applies no default**, deliberately. `vertex_tree_to_pandoc` is format-neutral, and
  the default depends on the format, the bundle mode, and the project type — none of which it
  knows. An unstamped occurrence means *nobody asked*; the format pass reads that as "apply my
  default".
- **Each format pass resolves and acts.** `pdf_placement.requested_pdf_render` reads the stamp or
  defaults it; `honoured_pdf_render` narrows it to what the format supports, warning on any
  fallback. `pdf_rendering._apply_pdf_embeds` then renders pages for `INLINE_NATIVE`; the
  reference-only formats share `pdf_placement.apply_reference_placements`, which unwraps a
  `NAME_ONLY` occurrence to bare text and leaves a link placement's link intact. Every pass
  consumes the scaffold, since Pandoc writers otherwise surface it (the GFM writer falls back to a
  raw HTML anchor for an attributed link).
- **The link's URL is already decided by the build**, which is why `INTERNAL_LINK` needs no special
  handling: bundle mode fetches every displayed asset into the bundle directory and hands the build
  filename-only paths, so links resolve to the copies beside the `.md`. Plain `--no-bundle` skips
  the fetch and builds with an empty asset map, leaving the remote URL. EPUB fetches assets but
  deliberately withholds `PdfVertex` entries from that map, since a PDF cannot be embedded in the
  package and a link to the temporary local path would be dead in the output.
- **A failed fetch** keeps the link to the remote source with the scaffold stripped, whatever the
  placement asked for.


## Format capabilities (verified 2026-07-27)

Facts established by direct test, recorded so they need not be re-derived:

- **Attaching a PDF to the PDF output is a dead end — settled, do not revisit.** Mechanically it is
  all possible: `pdf.attach("f.pdf")` (Typst 0.14.2; `pdf.embed` is the deprecated spelling) places
  the file in the document-level `/Names /EmbeddedFiles` table, and although Typst itself cannot
  link to it (`#link` compiles to a `/URI` action, and there is no `/AF` entry tying the attachment
  to the referencing page), the missing link can be synthesized in post-processing with **pypdf** —
  no PyMuPDF, so its AGPL licence never enters the picture. The clean technique is to have Typst
  emit a real link carrying a sentinel URI (`guffin-attachment:<name>`), so Typst lays out and
  positions the annotation, then swap only the action dictionary `/URI` → `/GoToE`; no coordinate
  arithmetic, and it survives reflow. **What defeats it is reader support, twice measured**: an
  investigation on 2026-07-06 hand-built PDFs exercising `/GoToE`, `/Launch`, `/FileAttachment`, and
  attachment-only, and macOS Preview honored none of them; the `/GoToE` route was re-tested on
  2026-07-27 and again does nothing in Preview, while Acrobat's handling is confusing. Hence the
  standing decision: the PDF format attaches nothing, and a `LINK` occurrence renders as plain
  filename text.
- **The remote URL is ciphertext.** A Roam-hosted asset URL returns HTTP 200 with
  `content-type: application/pdf`, but the bytes are the encrypted blob (`fe94 6f06 cf11 …`, not
  `%PDF-`) — decryption happens in the Roam client, which is why assets are fetched through the
  Local API. Every "remote link" cell above is therefore dead for a reader outside Roam, for as long
  as the graph is encrypted.


## Known wart

**The plain-`.md` label is degraded, and only there.** It shows the storage key
(`u-F9pv-nvn.pdf`) rather than the upload name (`dummy.pdf`), because the friendly name is learned
by fetching and `--no-bundle` skips the fetch. Combined with that format defaulting to
`EXTERNAL_LINK` — whose href is the encrypted asset — the output a human is most likely to read raw
carries both the least informative label and a link that only resolves for an unencrypted graph.
The `.enc` warning fires, so it is at least not silent.


## Design note: the appendix placements (vocabulary settled, behaviour unbuilt)

> **Status.** `APPENDIX_NATIVE` and `APPENDIX_IMAGE` are members of the vocabulary and are the
> default for `pdf` and `epub`, but **no format implements them yet** — every appendix request
> currently warns and falls back to `NAME_ONLY`. This section is the design for building them.

### The problem they solve

A `NAME_ONLY` occurrence renders as inert filename text: the reader is told a document exists and
given no way to reach it. The two obvious repairs are both closed. Linking to the original is
useless — the URL serves ciphertext outside the Roam client. Carrying the file as a PDF attachment
is a dead end measured twice: no viewer Guffin targets offers a usable way in (see *Format
capabilities* above).

Both repairs failed for the same reason — they tried to deliver the PDF *as a file*.

### The proposal

Deliver it as **rendered content that lives at the back of the document**:

- every PDF referenced by a `LINK`-placed occurrence gets a subsection under one generated
  back-matter section — *Appendix* — whose body is that PDF's pages, inlined exactly as
  `INLINE` already inlines them;
- the reference at the anchor point becomes an **internal link** to that subsection, rather than
  plain text or an external URL.

### Why it works where attachment did not

The navigation is an ordinary intra-document jump — a named destination, the same mechanism a table
of contents or a cross-reference uses. It is the one link type no reader breaks, and it is
completely independent of the embedded-file machinery that Preview ignores. The payload is not
hidden in a container the reader must know to look for: it is document content, in the flow,
reachable by scrolling even if every link in the file were dead.

It also inherits the properties of the existing inline path: Typst places each source page as a
**Form XObject**, so the attached pages keep their vector content — text stays selectable and
searchable in the host document, with no resolution to choose.

### Verified mechanics

Pandoc's Typst writer emits a Typst label from a header's identifier, so a raw-Typst link resolves
against a real Pandoc heading — no hand-built destinations:

```
= Appendix
<appendix>
== dummy.pdf
<att-dummy>
```

and the compiled result carries a plain internal link, not an action:

```
page 1: subtype=/Link dest=att-dummy action=None
```

### It is format-independent

Unlike attachment, this expresses in every output Guffin produces, which is what makes it a
legitimate member of a format-independent vocabulary rather than a PDF trick:

| format | attachments section | the anchor's reference |
|---|---|---|
| `pdf` | back-matter section, pages inlined per `#image(…, page: n)` | internal link to the subsection (verified) |
| `epub` | back-matter section, one subsection per PDF | intra-publication link (`<a href="chNNN.xhtml#id">`); *expected, unverified* |
| `md` | a heading per PDF | anchor link to the heading; whether pages can be *shown* depends on the format's image support |

### Where it would be built

In the **shared Doc build (Phase 1)**, not in `pdf_rendering._apply_pdf_embeds`'s post-build
rewrite. The Appendix section is real document structure, so building it there is what earns it
a ToC entry, the `unnumbered` exemption for non-body matter, an `epub:type`, and correct behaviour
under `promote_non_body_sections` — and it is what makes the EPUB and Markdown columns above fall
out of the existing machinery instead of needing three separate implementations. Only the page
images themselves stay format-specific.

### Decisions (2026-07-27)

- **The section is purely renderer-generated** — deliberately *not* a `StructuralElement` member,
  which would drag in follow-on vocabulary questions for no immediate gain. Consequences: the
  generated `Header` is stamped directly with what a tagged heading would have earned through the
  vocabulary — the `unnumbered` class and the back-matter `MATTER_DATA_ATTRIBUTE`, and an
  `epub:type` if wanted (`EpubType.APPENDIX` is the closest existing term) — rather than deriving
  them from an `element-type` tag. The trade accepted: an *authored* section of this kind is not
  recognized, so nothing dedupes a generated Appendix section against a hand-written one, the way
  `has_element_type` suppresses a duplicate generated ToC.
- **Deduplicate by source URL.** Two occurrences of one PDF produce one subsection, with both
  anchors linking to it; per-occurrence resolution already distinguishes the sites.
- **The section and every subsection appear in the ToC.** This does not conflict with being
  unnumbered: Pandoc emits an unnumbered heading as `#heading(level: n, numbering: none)[…]`, and a
  Typst `#outline()` still lists it (verified — the generated section and its subsection both appear in the
  generated Contents).
- **In a parts book it is a sibling of the parts**, never adopted by the last one. This falls out
  rather than needing work: `promote_non_body_sections` runs in Phase 0 over the model tree, and the
  section does not exist until Phase 1, so it is simply emitted at heading level 1 — which *is*
  sibling-of-parts in a parts book.
- **Built in the shared Doc build (Phase 1)**, not in `_apply_pdf_embeds`'s post-build rewrite.

### Still open

- **Is it a new `PdfRender` member, or a redefinition of `LINK`?** It is a third answer to *where do
  this PDF's pages go?* — at the anchor, at the back, or nowhere — which argues for a distinct
  member (`APPENDED`? `ATTACHED`? the naming is open) and for keeping a "named only, no pages"
  placement available. Which one an untagged embed defaults to is a separate decision. **This one
  blocks implementation**; the rest do not.
- **Cost.** A long attached PDF makes the export much larger and dominates the back matter; whether
  that wants a page limit, or is simply the author's call, is undecided.
