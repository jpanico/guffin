# EPUB resources

Bundled package data consumed only by `guffin/render/epub_rendering.py` when converting a
`VertexTree` to EPUB 3 via Pandoc.

EPUB content documents are XHTML, so these Pandoc Lua filters emit the same raw-HTML markup as
their `gfm_resources/` counterparts:

| Filter | Rewrites |
|---|---|
| `epub_alternatives.lua` | an `alternatives` `Div` (a versioned block's wordings under `--render-alternatives`: a `selected-wording` `Div`, then one `alternative-wording` `Div` per alternative) → a `Div.alternatives` of paragraphs, each led by a drawn inline-SVG radio marker (filled for the selected wording, hollow for each alternative, whose text is wrapped in `span.alternative-text`); `epub.css` draws the dashed rail, hangs each marker through a negative `text-indent`, and mutes the alternatives. The group always sits inside the text column — reading systems own the page margin and may clip into it. A `BulletList` holding a group is laid out whole: wrapped in `Div.alternatives-list` (native markers suppressed), the group becoming a `Div.alternatives.in-list` whose markers hang into the list indent beside its rail, and every other item led by a drawn dot of the same width (or its classification glyph), so all text edges line up. Registered **first**, so the bullet pass never sees a list it has already laid out |
| `epub_bullet.lua` | a `BulletList` containing classified items (the scaffold `Div` stamped with `data-guffin-marker-glyph`) → the list wrapped in `Div.semantic-bullets` with every item led by a `bullet-glyph` `Span` (the item's marker glyph — its semantic bullet, or a lone source channel's badge — or the plain default bullet for unclassified siblings); `epub.css` suppresses the wrapped list's native markers via `list-style: none` — no `::marker` and no `:has()`, which the Kindle app's renderer does not support |
| `epub_callout.lua` | prepends the shared SVG icon from `../callout_icons/` into each callout's `callout-title` header (icon + title, mirroring the gentle-clues PDF header) |
| `epub_color_span.lua` | Color Highlighter `Span`/`Div` elements → inline-styled `<span>`/`<mark>` (text color, highlight, underline-color, box, whole-line background) and the attribute-assignment `.pill` badge |
| `epub_mark.lua` | plain `.mark` `Span` → `<mark>` |
| `epub_number_lines.lua` | adds the `numberLines` class to every code block so skylighting emits per-line spans with line identities (matching the Typst/PDF numbering); after packaging, `epub_post_processing.bake_code_line_numbers` rewrites the CSS-counter gutter into literal-text numbers (`span.line-number`, styled by `epub.css`) for reading systems — notably the Kindle app — that do not implement the counter/positioning CSS |
| `epub_todo.lua` | a TODO checkbox glyph (`☐` U+2610 / `☒` U+2612) `Str` that does **not** open its `Plain`/`Para` — a reference's display amid text — → the glyph wrapped in a 1.2em inline-styled `<span>`, the DONE glyph displayed as `☑` (U+2611, the checkmark form matching the writer's native checkbox inputs); a glyph that *does* open its block is left bare, since on a list item that leading `Str` is what the writer's task-list conversion turns into a real `<input type="checkbox"/>` |

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
  writer renders the `<div class="fancy-quote">` (with its `fancy-quote-text` sub-`div`) natively, and
  `epub.css` supplies the whole pull-quote treatment (mirroring the PDF) — the serif register and the bold
  1.5x quotation with an oversize opening quote (a `::before` glyph on the first paragraph, hung in the
  left gutter by absolute positioning — except in the Kindle app, whose renderer ignores `position` and
  negative float margins, where an `amzn-kf8` media query floats it at the column edge as a drop cap the
  quotation flows beside). A pull quote
  carries no attribution: its source is the work itself. It carries **no** left bar (unlike the plain
  block quote), so the mark and large type carry the signal. Its serif `font-family` (shared with the
  callout body) is the customization point.
- **block-quote attribution** — likewise **no filter**: a block quotation's source line arrives as a
  `<div class="quote-attribution">` closing its `<blockquote>`, led by an em dash, and `epub.css` sets it
  upright against the quote's italic, on its own line left-aligned with the quotation.
- **epigraph** — likewise **no filter**: the epigraph ([[>]] [[!EPIGRAPH]]) arrives as
  `<div class="epigraph" epub:type="epigraph">` (Pandoc's EPUB writer keeps the `epub:type`), holding a
  `<div class="epigraph-text">` and, when attributed, a `<div class="epigraph-attribution">` led by an em
  dash, and `epub.css` sets it as the PDF does: a narrow column at the right of the text block, slightly
  smaller than body text, the quotation italic and ragged, the source flush right and upright.
- **captions** — likewise **no filter**: the `<div class="caption">` below an image or code listing
  (the block's own nested content, or — also classed `code-source` — the emphasized line naming the
  GitHub file a sourced listing was snapshotted from) survives to XHTML, and `epub.css` styles it as
  a caption — small, muted, pulled up toward the block it annotates.
- **authored page break** — likewise **no filter**: a heading tagged `page-break:: before` carries a
  `page-break-before` class that Pandoc propagates to the section wrapper, and `epub.css` applies
  `break-before: page` (plus the legacy `page-break-before: always`). Best-effort by nature —
  reading-system support for the property varies, and a section already opening a content document
  starts a page regardless.
