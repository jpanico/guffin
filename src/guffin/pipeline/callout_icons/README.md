# Callout icons

Bundled SVG badge icons for callout type indicators, **shared** by the PDF and EPUB output paths so
both formats render the same icon set.

One file per gentle-clues callout function:

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

Each icon is a filled accent-colored badge with a white symbol; the accent matches the callout's
border color in `epub_resources/epub.css`. The icons are self-colored (they do not inherit the
surrounding context), so a given callout type looks identical across formats.

Consumed at render time by:

- `pipeline/pdf_rendering.py` → `typst_resources/typst_callout.lua` — inlines the SVG into the
  gentle-clues `icon:` argument as `image(bytes(...), format: "svg")`.
- `pipeline/epub_rendering.py` → `epub_resources/epub_callout.lua` — inlines the SVG into the
  `callout-label` prepended to each callout `<div>`.

Both filters locate this directory via the Pandoc metadata field `callout-icons-dir`, set by the
respective renderer.
