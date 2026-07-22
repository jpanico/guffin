# EPUB resources

Bundled package data consumed only by `guffin/render/epub_rendering.py` when converting a
`VertexTree` to EPUB 3 via Pandoc.

EPUB content documents are XHTML, so these Pandoc Lua filters emit the same raw-HTML markup as
their `gfm_resources/` counterparts:

| Filter | Rewrites |
|---|---|
| `epub_callout.lua` | prepends the shared SVG icon from `../callout_icons/` into each callout's `callout-title` header (icon + title, mirroring the gentle-clues PDF header) |
| `epub_color_span.lua` | Color Highlighter `Span`/`Div` elements → inline-styled `<span>`/`<mark>` (text color, highlight, underline-color, box, whole-line background) and the attribute-assignment `.pill` badge |
| `epub_mark.lua` | plain `.mark` `Span` → `<mark>` |
| `epub_number_lines.lua` | adds the `numberLines` class to every code block so skylighting emits per-line spans with line identities (matching the Typst/PDF numbering); after packaging, `epub_post_processing.bake_code_line_numbers` rewrites the CSS-counter gutter into literal-text numbers (`span.line-number`, styled by `epub.css`) for reading systems — notably the Kindle app — that do not implement the counter/positioning CSS |

`epub.css` is the bundled default stylesheet, applied via Pandoc `--css`. It is the customization
point for the e-book's typeface — edit its `font-family` declarations to control the fonts.

Notes on GFM-pipeline constructs that are handled differently here:

- **callout** — the GFM filter emits GitHub blockquote-alert syntax, which is not valid XHTML, so it
  is not reused. The callout `<div class="callout callout-TYPE">` is styled by `epub.css` as a tinted
  header band over a white body, and `epub_callout.lua` (above) prepends the shared icon into the
  header. The callout **body** is set in a contrasting serif (`div.callout` `font-family`, mirroring
  the PDF's `callout-font`) so its content reads as a distinct register against the sans body; the
  title is reset to the sans body face (`div.callout-title` `font-family`). The per-type callout
  **colours** (left accent bar + header-band tint) are **not** in `epub.css`: they are generated
  from the canonical single-source palette (`guffin/render/callout_theme.py`) by `epub_rendering.py`
  into a second stylesheet loaded after `epub.css`, so the same colour drives every output format.
- **image** — the GFM image filter is not applied: Pandoc's EPUB writer natively embeds local-path
  images into the package, so content images must reach the writer as Pandoc `Image` elements rather
  than raw `<img>` HTML.
- **fancy quote** — the pull quote ([[>]] [[!QUOTE]]) needs **no filter** at all: Pandoc's EPUB
  writer renders the `<div class="fancy-quote">` (with its `fancy-quote-text` / `fancy-quote-attribution`
  sub-`div`s) natively, and `epub.css` supplies the whole pull-quote treatment (mirroring the PDF) — the
  serif register, the bold 1.5x quotation with an oversize opening quote (a `::before` glyph on the first
  paragraph), and the italic body-size attribution. It carries **no** left bar (unlike the plain block
  quote), so the mark and large type carry the signal. Its serif `font-family` (shared with the callout
  body) is the customization point.
- **code-source attribution** — likewise **no filter**: the `<div class="code-source">` below a sourced
  code listing (the emphasized line naming the GitHub file it was snapshotted from) survives to XHTML,
  and `epub.css` styles it as a caption — small, muted, pulled up toward the listing.
- **authored page break** — likewise **no filter**: a heading tagged `page-break:: before` carries a
  `page-break-before` class that Pandoc propagates to the section wrapper, and `epub.css` applies
  `break-before: page` (plus the legacy `page-break-before: always`). Best-effort by nature —
  reading-system support for the property varies, and a section already opening a content document
  starts a page regardless.
