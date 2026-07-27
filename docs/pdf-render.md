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

- **Typst can attach a file, but cannot link to the attachment.** `pdf.attach("f.pdf")` (Typst
  0.14.2; `pdf.embed` is the deprecated spelling) places the file in the PDF's document-level
  `/Names /EmbeddedFiles` table. There is no `/AF` entry on the catalog or on the page, so the
  attachment is not associated with the place in the text that references it, and `#link("f.pdf")`
  compiles to a `/URI` action with a relative URI rather than the `/GoToE` embedded-file action a
  reader needs. A PDF could therefore *carry* a referenced PDF, discoverable only through the
  viewer's attachments pane, with the in-text reference remaining plain text.
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
