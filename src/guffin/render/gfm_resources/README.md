# Guffin GFM Resources

This package bundles the [Pandoc Lua filters](https://pandoc.org/lua-filters.html) for the Markdown (GitHub-Flavored Markdown) output path (`md_rendering.py`). They translate the *generic* `Div` / `Span` / `Image` elements that `vertex_tree_to_pandoc` (in `pandoc_rendering.py`) emits into the GFM constructs and inline HTML that GitHub and Markdown previewers (e.g. Typora) render — output Pandoc's default GFM writer would not otherwise produce.

This is the Markdown counterpart to `pipeline/typst_resources/`, which holds the equivalent `typst_*.lua` filters (and the Bergfink template) for the PDF/Typst path.

## How they are loaded and executed

`md_rendering.py` converts the document by calling Pandoc through pypandoc, passing each filter with a `--lua-filter` argument (paths resolved from this package via `importlib.resources`):

```python
pypandoc.convert_text(json_str, "gfm", format="json", extra_args=[
    "--wrap=none",
    f"--lua-filter={gfm_dir / 'gfm_callout.lua'}",
    f"--lua-filter={gfm_dir / 'gfm_quote.lua'}",
    f"--lua-filter={gfm_dir / 'gfm_color_span.lua'}",
    f"--lua-filter={gfm_dir / 'gfm_image.lua'}",    # bundle mode only
    f"--lua-filter={gfm_dir / 'gfm_mark.lua'}",
    f"--lua-filter={gfm_dir / 'gfm_bracket.lua'}",
])
```

The input (`json_str`) is the Pandoc JSON AST (a serialized Panflute `Doc`). Pandoc applies the filters **in the order given** to the parsed AST, *before* the GFM writer serializes it. Each filter defines element-type functions (`Div`, `Span`, `Image`) that Pandoc invokes for every matching node, returning replacement node(s). Where a filter emits HTML (or Markdown) the writer should pass through verbatim, it inserts `RawInline` / `RawBlock` nodes tagged `"html"` (or `"markdown"`).

`gfm_image.lua` runs only in **bundle mode** (`--bundle`), where images are fetched into the `.mdbundle/` directory and need sized `<img>` tags. In plain mode (`--no-bundle`) images fall back to hyperlinks pointing at the original Cloud Firestore URLs, so the image filter is omitted.

## Filters

| Filter | Matches | Emits |
|---|---|---|
| `gfm_callout.lua` | a `Div` with a `callout-<type>` class (plus an optional `callout-title` sub-`Div`) | a [GFM alert](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts) blockquote — `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, or `> [!CAUTION]` — with the title as a bold first line |
| `gfm_quote.lua` | a `Div` with a `fancy-quote` class (its `fancy-quote-text` and optional `fancy-quote-attribution` sub-`Div`s) | a best-effort block quote: the quotation as a **bold** first line led by the `❝` (U+275D) ornament — a Dingbats glyph whose largeness is baked into the font, since plain Markdown cannot scale a character — the attribution as an *italic* line (inner same-type emphasis flattened to keep the Markdown valid) |
| `gfm_color_span.lua` | a color `Span` / `Div` carrying a `color`, `highlight-color` (with class `mark`), `underline-color`, `box-color`, or `bg-color` attribute | inline HTML: `<span style="color: …">`, `<mark style="background-color: …">`, an underline or bordered `<span>`, or a `<span style="background-color: …">`, with inner content preserved |
| `gfm_image.lua` | an `Image` (bundle mode) | `<img src="…" [alt] [width] [height] style="margin: 0;">`, with width/height read from the Pandoc attributes set by the rendering layer |
| `gfm_mark.lua` | a `Span` with class `mark` (and no `highlight-color`) | `<mark>…</mark>` |
| `gfm_bracket.lua` | a `Str` containing a literal `[` or `]` | the surrounding text as `Str` pieces with each bracket as a raw-HTML character entity (`&#91;` / `&#93;`) |

A few details worth noting:

- **`gfm_mark.lua` is the downstream handler for `roam_md_to_pandoc_md.py::convert_highlights()`.** That function turns Roam's `^^…^^` highlight into a `[text]{.mark}` span. Pandoc's GFM writer would otherwise render the span as an unstyled `<span class="mark">…</span>`, which GitHub and Typora do not highlight, so the filter rewrites it to a real `<mark>` element to preserve the highlight.
- **Filter order matters between `gfm_color_span.lua` and `gfm_mark.lua`.** `gfm_color_span.lua` runs first, so a `mark` span that also carries a `highlight-color` becomes a colored `<mark style="background-color: …">`; a plain `mark` span (no color) then falls through to `gfm_mark.lua` as a bare `<mark>`.
- **`gfm_callout.lua`** collapses Guffin's callout types onto GitHub's five alert types (e.g. `info` / `note` / `quote` / `example` / `summary` / `question` → `NOTE`, `tip` / `success` → `TIP`, `warning` → `WARNING`, `danger` / `failure` / `bug` → `CAUTION`).
- **`gfm_image.lua`** always emits `style="margin: 0;"` to keep a standalone image left-justified: some previewers (Typora) center an image that is the only child of its paragraph via `p > img:only-child { margin: auto }`, and the inline style overrides that.
- **`gfm_color_span.lua`** renders a `bg-color` `Div` as an inline `<span>` rather than a block element, because Typora does not render block-level HTML inside list items.
- **`gfm_bracket.lua`** exists for Typora too: Pandoc's GFM writer backslash-escapes literal brackets (`\[ … \]`), which is correct CommonMark, but Typora's MathJax layer misreads that sequence as LaTeX display-math delimiters and renders the content as math (italic, with Markdown left unparsed). The character entities render as plain brackets in every HTML-based previewer and can never be sniffed as math. Structural brackets — links, spans, code — are untouched, since they are not `Str` text.
