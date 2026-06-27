# EPUB resources

Bundled package data consumed only by `guffin/pipeline/epub_rendering.py` when converting a
`VertexTree` to EPUB 3 via Pandoc.

EPUB content documents are XHTML, so these Pandoc Lua filters emit the same raw-HTML markup as
their `gfm_resources/` counterparts:

| Filter | Rewrites |
|---|---|
| `epub_color_span.lua` | Color Highlighter `Span`/`Div` elements → inline-styled `<span>`/`<mark>` (text color, highlight, underline-color, box, whole-line background) and the attribute-assignment `.pill` badge |
| `epub_mark.lua` | plain `.mark` `Span` → `<mark>` |

`epub.css` is the bundled default stylesheet, applied via Pandoc `--css`. It is the customization
point for the e-book's typeface — edit its `font-family` declarations to control the fonts.

Two filters from the GFM pipeline are deliberately **not** applied to EPUB output:

- **callout** — the GFM filter emits GitHub blockquote-alert syntax, which is not valid XHTML.
  `CalloutVertex` instead passes through as a `<div class="callout callout-TYPE">`, styleable via a
  CSS stylesheet.
- **image** — Pandoc's EPUB writer natively embeds local-path images into the package, so the
  content must reach the writer as Pandoc `Image` elements rather than raw `<img>` HTML.
