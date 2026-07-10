# Guffin Typst Resources

This package bundles the resources for the PDF output path (`pdf_rendering.py`), of two kinds:

- the **Bergfink Typst template** — the `.typ` / `.typst` files that style the rendered document, and
- the **Pandoc Lua filters** — the `typst_*.lua` files that rewrite the Pandoc AST into Typst
  constructs the default Typst writer does not produce.

Both are resolved from this package at render time (via `importlib.resources`) and handed to Pandoc —
the template through `--template`, each filter through `--lua-filter`.

## Bergfink Typst template

The `.typ` and `.typst` files in this directory are the **Bergfink** Pandoc/Typst template, based on:

- **Repository**: [andyburri/pandoc-typst-template](https://github.com/andyburri/pandoc-typst-template)
- **Commit**: [`8abcbc1`](https://github.com/andyburri/pandoc-typst-template/commit/8abcbc177ad2e942ca1cd5ff41163205ac91a62b) (2026-05-18)

### Why Bergfink

- **Pandoc-native**: uses Pandoc's `$variable$` template syntax throughout, including `$body$`, so it slots directly into the `pypandoc.convert_text` call in `pdf_rendering.py` via `--template`.
- **Typst-based**: works with `--pdf-engine=typst`, consistent with the rest of the PDF pipeline.
- **Richly configurable**: exposes font, margins, paper size, title page, TOC, headers/footers, and more — all controllable via Pandoc `-V` variables or a `user_cfg.typ` override file, without editing the template itself.
- **No LaTeX dependency**: unlike the popular Eisvogel template (which requires a full LaTeX installation), Bergfink only needs Typst — already a project requirement.

### Files

| File | Purpose |
|---|---|
| `bergfink.typst` | Main template entry point — Pandoc injects variables and `$body$` here |
| `base_cfg.typ` | Default configuration values (font, margins, colors, etc.) |
| `user_cfg.typ` | Project-level overrides — edit this file to customize styling |
| `default_styles.typ` | Typst `#set` and `#show` rules that apply the config to the document |
| `titlepage.typ` | Title page layout |
| `abstract.typ` | Abstract and acknowledgements page layout |
| `toc.typ` | Table of contents layout |
| `yamltable.typ` | Helper for rendering YAML-defined tables |

### Font Requirements

The default configuration in `base_cfg.typ` uses **Noto Sans** (body, headings, headers/footers) and **Noto Sans Mono** (code blocks). Both must be installed on the system as **static** fonts (not variable fonts — Typst does not currently support variable fonts).

Callout boxes set their **body** in a contrasting serif via the `callout-font` key (default **Libertinus Serif**, which ships embedded with Typst and so needs no installation), so callout content reads as a distinct register against the sans body. The callout *title* keeps the ambient `font`. Override `callout-font` in `user_cfg.typ` to change (or, to disable the contrast, set it to the same value as `font`).

On macOS, download the static variants from Google Fonts: open the family page, click *Download family*, and install only the files from the `static/` subfolder via Font Book. Variable font files are identifiable by `[wght]` or `[wdth]` in their filename — do not install those.

To avoid this requirement entirely, override the font keys in `user_cfg.typ` with fonts already present on the system (e.g. `Helvetica Neue` and `Menlo` on macOS).

### Customization

Edit `user_cfg.typ` to override any default from `base_cfg.typ`. Define a `#let user_cfg = (...)` dictionary with only the keys you want to change — they are merged on top of the defaults.

### Modifications from upstream

The following changes have been made to the stock Bergfink distribution. When updating to a newer upstream commit, these modifications must be re-applied.

#### Per-level heading size, weight, and style (`base_cfg.typ`, `default_styles.typ`)

Nine new keys were added to the `cfg` dictionary in `base_cfg.typ`:

| Key | Type | Default | Description |
|---|---|---|---|
| `h1-size` | float | `1.3` | H1 font size as a ratio of `fontsize` |
| `h2-size` | float | `1.1` | H2 font size as a ratio of `fontsize` |
| `h3-size` | float | `1.0` | H3 font size as a ratio of `fontsize` |
| `h1-weight` | string | `"bold"` | H1 font weight (e.g. `"semibold"`, `"extrabold"`, or an integer 100–900) |
| `h2-weight` | string | `"bold"` | H2 font weight |
| `h3-weight` | string | `"bold"` | H3 font weight |
| `h1-style` | string | `"normal"` | H1 font style (`"normal"`, `"italic"`, or `"oblique"`) |
| `h2-style` | string | `"normal"` | H2 font style |
| `h3-style` | string | `"normal"` | H3 font style |

The defaults reproduce Typst's built-in heading appearance, so existing PDFs are unaffected. In `default_styles.typ`, the hardcoded size ratios and the H3 `#show` rule (which upstream omits a text rule for) were replaced with rules that read from `cfg`:

```typst
#show heading.where(level: 1): set text(fontsize * cfg.h1-size, weight: cfg.h1-weight, style: cfg.h1-style)
#show heading.where(level: 2): set text(fontsize * cfg.h2-size, weight: cfg.h2-weight, style: cfg.h2-style)
#show heading.where(level: 3): set text(fontsize * cfg.h3-size, weight: cfg.h3-weight, style: cfg.h3-style)
```

These keys are overridable in `user_cfg.typ` like any other `cfg` key.

#### Table of contents controlled by `cfg.toc` (`bergfink.typst`, `toc.typ`)

In the stock template, the TOC is gated by a Pandoc template variable (`$if(toc)$`), which is set only when Pandoc is invoked with `--toc` or `-V toc`. Because `pdf_rendering.py` never passes that flag, setting `toc: true` in `user_cfg.typ` had no effect.

`bergfink.typst` was changed to always include `$toc.typ()$` (removing the `$if(toc)$` guard). `toc.typ` was rewritten to wrap its entire body in `#if cfg.toc { ... }`, so the TOC renders if and only if `cfg.toc` is `true`. Typst's `set page` rule is explicitly not scoped to blocks (unlike other set rules), so TOC page numbering (`cfg.toc-page-numbering`) is still applied correctly when the TOC is enabled.

#### Heading numbering start level (`base_cfg.typ`, `default_styles.typ`)

A new `heading-numbering-start-level` key was added to the `cfg` dictionary in `base_cfg.typ`:

| Key | Type | Default | Description |
|---|---|---|---|
| `heading-numbering-start-level` | int | `1` | Minimum heading level that receives a section number; headings above this level are unnumbered |

The default (`1`) numbers all heading levels, preserving the upstream behavior. Setting it to `2` suppresses numbering on H1 while numbering H2 and deeper, with counters relative to H2 (so the first H2 shows as `1.`, not `1.1.`).

In `default_styles.typ`, the simple `numbering = cfg.section-numbering` assignment was replaced with a function that drops the counter prefix for levels below the start:

```typst
numbering-fn = (..args) => {
  let nums = args.pos()
  if nums.len() < start {
    none
  } else {
    numbering(fmt, ..nums.slice(start - 1))
  }
}
```

This key has no effect unless `number-sections` is also `true`.

#### Title-page publisher and rights (`base_cfg.typ`, `bergfink.typst`, `titlepage.typ`)

Two new keys were added to the `cfg` dictionary in `base_cfg.typ`, for title-page parity with
Pandoc's generated EPUB title page (which renders both fields natively):

| Key | Type | Default | Description |
|---|---|---|---|
| `publisher` | string/none | `none` | Publisher name, rendered above the date at the title-page foot |
| `rights` | string/none | `none` | Rights statement, rendered in small text below the date line |

`bergfink.typst` maps the Pandoc `publisher` and `rights` metadata variables into these keys
(alongside the existing `title`/`subtitle` mappings), and `titlepage.typ` renders them at the page
foot mirroring the Pandoc EPUB field order (publisher, date, rights). Both default to `none`, so
documents without the metadata are unaffected.

The subtitle guard in `titlepage.typ` was also tightened from `!= none` to `not in (none, "")`:
the `base_cfg.typ` default is the empty string, which previously left a stray `v(0.65em)` spacer
on title pages without a subtitle.

#### Book mode (`bergfink.typst`)

A template block gated on the Pandoc `top-level-division` variable (passed by `pdf_rendering.py` as
`-V top-level-division=chapter|part` for book projects; never passed for the default section
layout, which therefore stays byte-identical). When active, the block:

- adds a `pagebreak(weak: true)` show rule before every **level-1** heading (the top division —
  chapters, or parts in a parts book — opens on a new page);
- when the division is `part`, adds the same page break before every **level-2** heading, since
  that is where a parts book's chapters live;
- overrides heading numbering with a hierarchical join (`1`, `1.1`, `1.1.1`) starting at level 1
  when `cfg.number-sections` is enabled, matching Pandoc's EPUB `--number-sections` output.

#### Provenance colophon (`base_cfg.typ`, `bergfink.typst`, `titlepage.typ`, `default_styles.typ`)

Two new keys were added to the `cfg` dictionary in `base_cfg.typ`, backing the export provenance
colophon (`export-roam-tree --colophon`; the summary text is supplied by `pdf_rendering.py` as a
Pandoc variable — `titlepage-provenance` when a title page is emitted, else `footer-provenance`):

| Key | Type | Default | Description |
|---|---|---|---|
| `titlepage-provenance` | string/none | `none` | Provenance line rendered in small gray text at the very foot of the title page |
| `footer-provenance` | string/none | `none` | Provenance line rendered centered in small gray text below the running page footer |

`bergfink.typst` maps the two Pandoc variables into these keys; `titlepage.typ` renders
`titlepage-provenance` below the date/rights block, and `default_styles.typ` renders
`footer-provenance` inside the page-footer rule. Both default to `none`, so documents rendered
without a colophon are unaffected.

#### Breakable tables (`default_styles.typ`)

Pandoc wraps every table in a Typst `figure` (`#figure(align(center)[#table(...)])`), and Typst
figures are `breakable: false` by default — so a table taller than the page would overflow and
render its overflow rows on top of one another. `default_styles.typ` adds
`#show figure.where(kind: table): set block(breakable: true)` so tall tables break across page
boundaries instead (Typst repeats the `table.header` row on each continuation page).

#### W3CDTF reduced-precision dates (`bergfink.typst`, `default_styles.typ`, `titlepage.typ`)

Upstream parses the Pandoc `date` variable by splitting on `-` and blindly indexing parts 0/1/2
into a Typst `datetime`, so any value that is not a full `YYYY-MM-DD` panics the compile
(`array index out of bounds`). Publishing metadata legitimately uses the W3CDTF reduced-precision
forms — `YYYY` (the CMOS-canonical publication date) and `YYYY-MM` — so the parse block in
`bergfink.typst` now builds a `datetime` only when three parts are present and otherwise leaves
`cfg.date` as the original string. A `display_date(date, dateformat)` helper (defined in
`bergfink.typst`, used by the header/footer `%date%` replacement in `default_styles.typ` and the
title-page foot in `titlepage.typ`) formats a `datetime` through `cfg.dateformat` and renders a
reduced-precision string verbatim. The PDF metadata (`#set document(date:)` in
`default_styles.typ`) takes only `datetime | auto | none`, so a reduced-precision date is omitted
there rather than fabricated. Guffin validates the `guffin-meta:: date:` value to the same W3CDTF
forms at export time (`publishing_semantics.all_date_values_legal`), so the template's fallback
path only ever sees `YYYY` or `YYYY-MM`.

### Updating

To update to a newer upstream commit, re-copy the files from the repository above, update the commit reference in this README, and re-apply the modifications described above.

## Pandoc Lua filters

The `typst_*.lua` files are [Pandoc Lua filters](https://pandoc.org/lua-filters.html). They exist because `vertex_tree_to_pandoc` (in `pandoc_rendering.py`) encodes Roam-specific constructs as *generic* Pandoc `Div` / `Span` elements carrying classes and attributes; these filters translate those generic elements into the Typst markup the Bergfink template expects, which Pandoc's default Typst writer would not otherwise emit.

### How they are loaded and executed

`pdf_rendering.py` converts the document by calling Pandoc through pypandoc, passing each filter with a `--lua-filter` argument (paths resolved from this package):

```python
pypandoc.convert_text(json_str, "typst", format="json", extra_args=[
    "--pdf-engine=typst",
    f"--template={bundled_dir / 'bergfink.typst'}",
    f"--resource-path={bundled_dir}",
    f"--lua-filter={bundled_dir / 'typst_callout.lua'}",
    f"--lua-filter={bundled_dir / 'typst_color_span.lua'}",
    f"--lua-filter={bundled_dir / 'typst_list_para.lua'}",
    # …
])
```

The input (`json_str`) is the Pandoc JSON AST (a serialized Panflute `Doc`). Pandoc applies the filters **in the order given** to the parsed AST, *before* the Typst writer serializes it. Each filter defines element-type functions (`Div`, `Span`, `BulletList`, …) that Pandoc invokes for every matching node, returning replacement node(s). Where a filter needs to emit Typst that the writer would otherwise escape, it inserts `RawBlock` / `RawInline` nodes tagged `"typst"`, which the writer passes through verbatim.

These filters apply only to the PDF/Typst path. The Markdown/GFM path uses a parallel set of `gfm_*.lua` filters in `pipeline/gfm_resources/`.

### Filters

| Filter | Matches | Emits |
|---|---|---|
| `typst_callout.lua` | a `Div` with a `callout-<type>` class (plus an optional `callout-title` sub-`Div`) | a [gentle-clues](https://typst.app/universe/package/gentle-clues) callout call (`info[…]`, `warning[…]`, `tip[…]`, …) — `bergfink.typst` imports the gentle-clues package |
| `typst_color_span.lua` | a color `Span` / `Div` carrying a `color`, `highlight-color` (with class `mark`), `underline-color`, `box-color`, or `bg-color` attribute | `#text(fill: …)`, `#highlight(fill: …)`, `#underline[…]`, `#box(stroke: …)`, or a full-width `#block(fill: …)`, with inner content preserved |
| `typst_list_para.lua` | a list item whose leading `Plain` block is immediately followed by a non-list block | promotes that `Plain` to a `Para`, keeping the leading text and the following block (e.g. an image) as separate Typst paragraphs |

A couple of details worth noting:

- **`typst_callout.lua`** maps each Guffin callout type to a gentle-clues function (e.g. `note` / `quote` → `memo`, `summary` → `conclusion`, `failure` / `bug` → `error`). It wraps the call in a Typst code scope `#{ … }` with a local `set par(first-line-indent: 0pt, justify: false)`, so the template's global paragraph rules do not leak into the callout, and passes the title as a Typst string literal. It also emits `#set text(font: cfg.callout-font)` at the head of the callout's content block, giving the callout **body** its contrasting serif face while the title keeps the ambient `font`. Each callout's `accent-color` is set from the canonical per-type palette (`guffin/render/callout_theme.py`, passed in via the `GUFFIN_CALLOUT_COLORS` env var), overriding gentle-clues' own theme colours so PDF callout colours match every other output format; gentle-clues derives the title band (`accent.lighten(85%)`) and box border from that one accent.
- **`typst_list_para.lua`** leaves nested lists untouched — a sublist already starts its own block and never merges, so only a non-list following block needs the paragraph break.
