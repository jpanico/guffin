# Design tokens

How a visual design language reaches every output format from one declaration.  The language
itself, the palette with its meanings, the type scale, the panel → card → row nesting, and the
rules for drawing a diagram to it, is a project's, not Guffin's; the values in force today are
the SCFH book's, kept in that project's `design/visual-design-language.md`.  This document covers
the mechanism: what a token is here, where the tokens are declared, and how the PDF and the
EPUB each derive their styling from them.

## The tokens

`src/guffin/render/design_language.py` declares the tokens once:

- **Colour families** (`DesignFamily`, `FAMILY_PALETTE`): each family has a *fill* (a light
  background), a *stroke* (a hairline outline), an *emphasis* stroke (the heavier outline of the
  one element being pointed at, and the frame of a card of the family), and an *ink* (the dark
  text that names an element), plus a `meaning`, the kind of thing the hue stands for.  The
  neutral inks `TEXT_INK`, `LABEL_INK`, and `MUTED_INK` stand apart for titles, labels, and
  descriptions.
- **Themes**: a styled element is a *card* of one family — white, framed by the family's
  emphasis stroke on a rounded outline, with a band of the family's fill carrying the family's
  ink in a semibold weight.  `TableTheme` / `TABLE_THEME` (a table: the header row is the band,
  body rows are parted by hairlines in the family's stroke, columns by padding alone) and
  `CalloutTheme` / `CALLOUT_THEME` (a callout box: the title band carries the icon and title,
  the body sits beneath, parted by the frame stroke; without a body the band stands alone).
  Every length is in ems of the element's text, so the look scales with the type.
- **The callout's family** is chosen by its type, declared once in
  `src/guffin/render/callout_theme.py` (`CALLOUT_FAMILY`, covering every `CalloutType`).

No bundled resource carries a family colour of its own: `tests/render/test_design_language.py`
checks `base_cfg.typ`, `user_cfg.typ`, and `epub.css` for any palette member.

## How each format derives its styling

**PDF.**  `typst_table_tokens()` and `typst_callout_tokens()` render each theme as a Typst
dictionary literal of Bergfink `cfg` keys.  `pdf_rendering` passes each as a `design-tokens`
template variable (the variable repeats, one per theme), and `bergfink.typst` joins every one
onto `cfg` after `base_cfg.typ` and before `user_cfg.typ`, so a user config, bundled or passed
as a `template_dir`, still overrides any key.  `default_styles.typ` applies them: the table
frame is a block clipped to `table-radius` and stroked with `table-frame-stroke`, the header
row's text takes `table-header-ink` and `table-header-weight`, and Pandoc's rule under the header
takes `table-stroke-header-b`; the template's own `callout` helper draws a callout from the
`callout-*` keys and `callout-colors` (per kind: `fill`, `frame`, `ink`), replacing
`currentColor` in the icon's SVG with the ink, since Typst gives an image no text colour.

**EPUB.**  `table_css()` and `callout_css()` render the same themes as stylesheet rules for
Pandoc's table markup and the shared build's `div.callout` markup, written by `epub_rendering`
to `design_tokens.css` and loaded after `epub.css`, which carries no table styling and no
callout colour or measure of its own.  The inline SVG icon inherits the title band's `color`.

**Markdown.**  Nothing: a GFM table is unstyled and a callout is a GitHub alert, whose look
GitHub owns.

| Language element | Token | PDF (`cfg` key) | EPUB (rule) |
|---|---|---|---|
| Card outline: the emphasis stroke | `frame_width_em` × family emphasis | `table-frame-stroke` | `table { border }` |
| Card radius | `radius_em` | `table-radius` | `table { border-radius }` + the two top `th` corners |
| Header band: the family fill | family fill | `table-header-bg` | `thead th { background-color }` |
| Header text: the family ink, semibold | family ink, `header_weight` | `table-header-ink`, `table-header-weight` | `thead th { color; font-weight }` |
| Header's lower edge: the emphasis stroke | as the frame | `table-stroke-header-b` | `thead th { border-bottom }` |
| Row parting: the hairline in the family stroke | `rule_width_em` × family stroke | `table-stroke-horizontal` | `tbody tr + tr td { border-top }` |
| Columns parted by space | — | the border and vertical strokes `none` | `th, td { border: 0 }` |
| Cell padding | `inset_x_em`, `inset_y_em` | `table-inset` | `th, td { padding }` |
| Striped rows (YAML tables, PDF only): the neutral fill | neutral family fill | `table-striped-bg` | — |

| Callout element | Token | PDF (`cfg` key) | EPUB (rule) |
|---|---|---|---|
| Frame and the rule under the band | `frame_width_em` × family emphasis | `callout-frame-width`, `callout-colors.<kind>.frame` | `div.callout { border }`, `div.callout-title { border-bottom }` |
| Card radius | `radius_em` | `callout-radius` | `div.callout { border-radius }` + the band's own corners |
| Title band | family fill, family ink, `title_weight` | `callout-colors.<kind>.fill` / `.ink`, `callout-title-weight` | `div.callout-title { background-color; color; font-weight }` |
| Band and body insets | `header_inset_*_em`, `body_inset_*_em` | `callout-header-inset`, `callout-body-inset` | `div.callout-title { padding }`, `div.callout { padding }` |
| Icon | `icon_size_em`; drawn in `currentColor` | `callout-icon-size` | `div.callout-title svg { width; height }` |

## Known gaps

- **Headerless tables.**  The PDF tints row 0 whether or not it is a header (Bergfink's fill
  keys on the row, as it always did); the EPUB tints only a real `<thead>`.  The EPUB's is the
  truer reading, and the PDF could be brought to it.
- **Vertical rules.**  Tables draw none.  A wide table with many short columns may want them
  back: `table-stroke-vertical` is the one key to set, in a `user_cfg.typ`.
- **Reading systems.**  The EPUB's rounded corners rely on `border-radius` and `:last-child`;
  a system without them (the Kindle app is the doubtful one) shows squarer boxes.
- **One project's values.**  The tokens are the SCFH book's, hard-coded here.  A theme file a
  project supplies beside its `user_cfg.typ` is the intended home once a second project needs
  different values.
