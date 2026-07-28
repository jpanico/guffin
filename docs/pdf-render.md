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


## What appears in the document text

| `PdfRender` | `md --bundle` | `md --no-bundle` | `pdf` | `epub` |
|---|---|---|---|---|
| **`INLINE`** | *tag ignored* — relative link `[dummy.pdf](dummy.pdf)` | *tag ignored* — remote link, label is the **storage key** `[u-F9pv-nvn.pdf](https://…enc)` | **honoured** — one full-width `#image(…, page: n)` per page, replacing the reference | *tag ignored* — remote link `[dummy.pdf](https://…enc)` |
| **`LINK`** (default) | relative link `[dummy.pdf](dummy.pdf)` | remote link, label is the **storage key** | **plain text** `dummy.pdf`, hyperlink dropped | remote link `[dummy.pdf](https://…enc)` |
| *fetch failed* | remote link | remote link | remote link (scaffold stripped) | remote link |


## Does the PDF file travel with the output?

| `PdfRender` | `md --bundle` | `md --no-bundle` | `pdf` | `epub` |
|---|---|---|---|---|
| **`INLINE`** | **yes** — copied into `.mdbundle/` | no | no — fetched to a temp dir, rasterized, discarded | no |
| **`LINK`** | **yes** — copied into `.mdbundle/` | no | no — fetched only to learn the label | no |


## Where each cell is decided

- **The shared build** renders every PDF occurrence as a `Para` holding one `Link`, labelled with
  the original upload filename when known (else the storage-key filename, Roam's `.enc` suffix
  stripped), pointing at the fetched local file when there is one and at the remote Cloud Firestore
  source otherwise. The resolved placement rides the link as the `PDF_PLACEMENT_ATTRIBUTE` scaffold
  (`render/pandoc_rendering._pdf_vertex_to_blocks`).
- **PDF** is the only format that consumes the scaffold: `pdf_rendering._apply_pdf_embeds` replaces
  an `INLINE` occurrence with one raw Typst `image(…, page: n)` per page, and a `LINK` occurrence
  with its bare label text — dropping the hyperlink, since the file is not carried into the output.
- **Markdown and EPUB** both call `strip_pdf_placement`, which removes the scaffold without reading
  it (an attributed link would otherwise fall back to a raw HTML anchor in the GFM writer). That is
  why the tag has no effect in either.
- **Bundling** is decided by `--bundle`, not by the tag: bundle mode fetches every displayed asset
  into the bundle directory and hands the build filename-only paths, so the links resolve to the
  copies beside the `.md`. Plain `--no-bundle` skips the fetch entirely and builds with an empty
  asset map. EPUB fetches assets but deliberately withholds `PdfVertex` entries from that map, since
  a PDF cannot be embedded in the package and a link to the temporary local path would be dead in
  the output (`epub_rendering`).


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


## Observations

Three things the matrix makes plain:

1. **The bundling table has no vertical variation.** Both rows are identical in every column: the
   file travels iff `--bundle`, never because of the tag. Presentation (pages vs. reference) and
   packaging (do the bytes travel) are separate axes, and `pdf-render` has no say in the second.
2. **`INLINE` is silently ignored in three of four outputs.** Tagging a PDF `inline` and exporting
   EPUB yields a link with no indication the directive was dropped — unlike `page-break::`, which
   logs a warning per dropped tag when a book's policy declines it.
3. **The plain-`.md` label is degraded, and only there.** It shows the storage key
   (`u-F9pv-nvn.pdf`) rather than the upload name (`dummy.pdf`), because the friendly name is
   learned by fetching and `--no-bundle` skips the fetch. Combined with the encrypted href, the one
   output a human is most likely to read raw carries both the least informative label and a dead
   link.


## Design note: an Attachments-section placement (proposed, not implemented)

> **Status: a proposal.** Nothing in this section is built. Everything above it describes current
> behaviour.

### The problem

A `LINK` occurrence in the PDF format renders as inert filename text: the reader is told a document
exists and given no way to reach it. The two obvious repairs are both closed. Linking to the
original is useless — the URL serves ciphertext outside the Roam client. Carrying the file as a PDF
attachment is a dead end measured twice: no viewer Guffin targets offers a usable way in (see
*Format capabilities* above).

Both repairs failed for the same reason — they tried to deliver the PDF *as a file*.

### The proposal

Deliver it as **rendered content that lives at the back of the document**:

- every PDF referenced by a `LINK`-placed occurrence gets a subsection under one generated
  back-matter section — *Attachments* — whose body is that PDF's pages, inlined exactly as
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
= Attachments
<attachments>
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
rewrite. The Attachments section is real document structure, so building it there is what earns it
a ToC entry, the `unnumbered` exemption for non-body matter, an `epub:type`, and correct behaviour
under `promote_non_body_sections` — and it is what makes the EPUB and Markdown columns above fall
out of the existing machinery instead of needing three separate implementations. Only the page
images themselves stay format-specific.

### Open questions

- **Is it a new `PdfRender` member, or a redefinition of `LINK`?** It is a third answer to *where do
  this PDF's pages go?* — at the anchor, at the back, or nowhere — which argues for a distinct
  member (`APPENDED`? `ATTACHED`? the naming is open) and for keeping a "named only, no pages"
  placement available. Which one an untagged embed defaults to is a separate decision.
- **Section identity.** Should *Attachments* be a `StructuralElement` member, so it can be
  recognized (and an authored section of that type respected, the way `has_element_type` suppresses
  a duplicate generated ToC), or purely renderer-generated?
- **Deduplication.** Two occurrences of one PDF should produce one subsection with both anchors
  linking to it — keyed by source URL, since per-occurrence resolution already distinguishes the
  sites.
- **Book interaction.** A level-1 *Attachments* heading in a parts book must land as a sibling of
  the parts, not be adopted by the last one — the case `promote_non_body_sections` exists for.
- **Cost.** A long attached PDF makes the export much larger and dominates the back matter; whether
  that wants a page limit, or is simply the author's call, is undecided.
