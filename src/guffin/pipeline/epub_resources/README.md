# EPUB resources

Bundled package data consumed only by `guffin/pipeline/epub_rendering.py` when converting a
`VertexTree` to EPUB 3 via Pandoc.

EPUB content documents are XHTML, so these Pandoc Lua filters emit the same raw-HTML markup as
their `gfm_resources/` counterparts:

| Filter | Rewrites |
|---|---|
| `epub_callout.lua` | prepends the shared SVG icon from `../callout_icons/` into each callout's `callout-title` header (icon + title, mirroring the gentle-clues PDF header) |
| `epub_color_span.lua` | Color Highlighter `Span`/`Div` elements → inline-styled `<span>`/`<mark>` (text color, highlight, underline-color, box, whole-line background) and the attribute-assignment `.pill` badge |
| `epub_mark.lua` | plain `.mark` `Span` → `<mark>` |
| `epub_number_lines.lua` | adds the `numberLines` class to every code block so skylighting emits line numbers (matching the Typst/PDF output) |

`epub.css` is the bundled default stylesheet, applied via Pandoc `--css`. It is the customization
point for the e-book's typeface — edit its `font-family` declarations to control the fonts.

Notes on two GFM-pipeline filters that are handled differently here:

- **callout** — the GFM filter emits GitHub blockquote-alert syntax, which is not valid XHTML, so it
  is not reused. The callout `<div class="callout callout-TYPE">` is styled by `epub.css` as a tinted
  header band over a white body, and `epub_callout.lua` (above) prepends the shared icon into the
  header.
- **image** — the GFM image filter is not applied: Pandoc's EPUB writer natively embeds local-path
  images into the package, so content images must reach the writer as Pandoc `Image` elements rather
  than raw `<img>` HTML.
