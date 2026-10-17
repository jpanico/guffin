# Callout icons

Bundled SVG badge icons for callout type indicators, **shared** by the PDF and EPUB output paths so
both formats render the same icon set.

One file per callout kind:

| File | guffin callout types |
|---|---|
| `info.svg` | info |
| `memo.svg` | note, quote |
| `example.svg` | example |
| `conclusion.svg` | summary |
| `question.svg` | question |
| `tip.svg` | tip |
| `success.svg` | success |
| `warning.svg` | warning |
| `danger.svg` | danger |
| `error.svg` | failure, bug |

Each icon is a filled badge with a white symbol, and the badge is drawn in `currentColor`: the icon
carries no colour of its own, and takes the ink of the callout it sits in — the family colour the
visual design language gives the callout's type (`guffin/render/callout_theme.py`, on
`guffin/render/design_language.py`; see `docs/visual-design-language.md`) — so one set of files
serves every family and a given callout type looks identical across formats.

Consumed at render time by:

- `render/pdf_rendering.py` → `typst_resources/typst_callout.lua` — passes the SVG source as a
  string to the template's `callout` helper (`default_styles.typ`), which replaces `currentColor`
  with the callout's ink and draws it with `image(bytes(...), format: "svg")`, since Typst gives
  an image no text colour to inherit.
- `render/epub_rendering.py` → `epub_resources/epub_callout.lua` — inlines the SVG into each
  callout's `callout-title` header, where it inherits the band's `color`.

Both filters locate this directory via the `GUFFIN_CALLOUT_ICONS_DIR` environment variable, set by
the respective renderer.
