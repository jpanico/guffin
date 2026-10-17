# Visual design language

The visual language that the book's illustrations, diagrams, and the PDF output's styled
elements share: one palette, one type system, one way of nesting, stroking, rounding, and
spacing things.  It was read off the chapter 1 *Stored-Program Computer* diagram (SCFH block
`((AWkkZ6CJG))`, a child of the page's `Claude` block), the first diagram drawn for the book,
and is written down here so that every later diagram can be drawn to it rather than to a fresh
guess, and so that the typeset elements of the PDF (today: tables) can follow the same rules.

Two audiences: whoever draws the next diagram (the **tokens** and **rules** sections give the
values to use), and whoever styles PDF output (the **PDF mapping** section says which Bergfink
`cfg` key carries each token).

## The idea in one paragraph

Everything is a light, tinted **panel** holding white **cards** holding white **rows**, three
levels of nesting, each a step smaller in corner radius and padding.  Every hue family has
three members, a *fill*, a *stroke*, and an *ink*, and an element uses one family throughout:
its background is the fill, its outline the stroke, and the text that names it the ink.  Lines
are thin and tinted, never black; the one thing drawn in a strong colour is the thing being
pointed at, the current step or the current instruction, and it gets the family's darker,
heavier stroke.  Elements are parted by space, not by rules.  Type is a humanist sans at a
semibold weight for names and a regular weight in a muted ink for descriptions, with a
matching mono for anything the machine reads.

## Tokens

### Palette

Five families.  The ink family is neutral text; the four hue families each carry a meaning in
the book's diagrams, listed so that the next diagram reuses the meaning rather than the colour
alone.

| Family | Meaning | Fill (background) | Stroke (outline) | Emphasis stroke | Ink (text) |
|---|---|---|---|---|---|
| Ink | text on white | — | — | — | `#161A22` titles and names; `#3D4250` labels, arrows, neutral panel names; `#5A6170` descriptions |
| Blue | the processor: the CPU, its steps, anything that acts | `#EDF2FA` | `#C8D5EA` | `#AFC0DC` | `#234279` |
| Neutral | the container: memory, storage, a holder of other things | `#F5F5F3` | `#DADAD5` | — | `#3D4250` |
| Amber | instructions and code: the program as text | `#FBEEE1` | `#EDD3B8` row `#E6C3A0`; current `#C96F2A` | `#C96F2A` | label `#8E4A12`; code `#3B2614` |
| Teal | data: values the program reads and writes | `#E6F2EF` | `#BFDCD5` row `#AFD2CA` | — | label `#1E5F54`; code `#173F39` |

White `#FFFFFF` is the canvas and every card's fill.  A family's *emphasis stroke* is what
the one highlighted element of its kind gets (the blue step cards, the current amber
instruction); plain siblings get the ordinary stroke.  Badges (the numbered step discs) are a
solid disc of the family's ink with white text.

### Typography

| Role | Face | Size | Weight | Notes |
|---|---|---|---|---|
| Diagram title | sans | 28 | 600 | tracking −1 % (`letter-spacing: -0.28` at 28) |
| Panel name | sans | 20 | 600 | tracked caps, +10 % (`letter-spacing: 2` at 20); ink: the family's ink |
| Card title | sans | 18 | 600 | ink `#161A22` |
| Section label inside a panel | sans | 14 | 600 | ink: the family's label ink |
| Description, arrow label | sans | 14 | 400 | ink `#5A6170` (descriptions) or `#3D4250` (arrow labels) |
| Badge numeral | sans | 12–13 | 600 | white on the family's ink |
| Code, values | mono | 15 | 400; keyword 600 | ink: the family's code ink |

Sizes are the diagram's own pixels, on a 1044 × 728 canvas; they are a *scale*, and the ratios
are what to keep when a diagram is drawn at another size.  The faces are **IBM Plex Sans** and
**IBM Plex Mono**, with the SVG fallback chains `'IBM Plex Sans', 'Helvetica Neue', Helvetica,
Arial, sans-serif` and `'IBM Plex Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace`.

### Structure

Three levels of nesting, each with its own radius, stroke, and padding.  The ratios are given
against the 14–15 px text the diagram is set in, so they can be reapplied at any size.

| Level | Example | Fill | Stroke | Corner radius | Padding |
|---|---|---|---|---|---|
| Panel | CPU, MEMORY | the family's fill | 1 px, the family's stroke | 13.5 px ≈ 0.9 em | 24 px ≈ 1.6 em to the name; cards inset 24 px |
| Card | a step; the Instructions or Data group | white (a step) or the family's fill (a group) | 1.5 px emphasis stroke (a step), 1 px family stroke (a group) | 9.25–9.5 px ≈ 0.625 em | 16 px ≈ 1.1 em |
| Row | one instruction, one value | white | 1 px, the family's row stroke; the current row 1.5 px emphasis | 5.25–5.5 px ≈ 0.375 em | 15 px ≈ 1 em horizontal; rows 35 px tall at 15 px text |

Spacing: rows sit 9 px apart (a 44 px pitch for 35 px rows); step cards sit 58 px apart with the
flow arrow in the gap; the two panels are 180 px apart with the buses in the gap.  Nothing
touches: parting is by space.

### Lines and arrows

| Element | Stroke | Ends |
|---|---|---|
| Hairline (panel, group, row outlines) | 1 px, the family's stroke tint | — |
| Emphasis (step card, current row) | 1.5 px, the family's emphasis stroke | — |
| Flow arrow within a panel | 2 px, the family's ink (`#234279` in the CPU), round caps and joins | filled triangular head, 9 px long × 9 px wide |
| Bus between panels | 2 px, neutral ink `#3D4250`, round caps | the same head; label 14 px / 400 in `#3D4250`, centred above the line |
| Loop | the same 2 px line, broken around the label that sits on it | — |

Arrows are drawn last, over the panels.

## Rules for a new diagram

1. White canvas; the title top-left in the title style; nothing framed by a border around
   the whole drawing.
2. Decide what each thing *is* and give it the family with that meaning: processing is blue,
   containment is neutral, code is amber, data is teal.  A new kind of thing gets a new
   family, declared here, with all three members chosen at the same lightness as its peers
   (fills around 95 % luminance, strokes around 85 %, inks dark enough for text).
3. Nest panel → card → row, never deeper, and step the radius and padding down at each level.
4. One element per family may be emphasised, with the family's heavier, darker stroke.  Everything
   else is a hairline.
5. Name things in semibold; describe them in regular, muted ink; set code in the mono.
6. Part elements by space.  Rules and dividers are a last resort.
7. Write the diagram as an SVG with a `<title>` and `<desc>` (the chapter 1 diagram's `desc`
   is a one-paragraph description of what it shows), the two font classes declared once in a
   `<style>`, and one `<g id>` per panel and per step.

## The tokens in code

The tokens are declared once, in `src/guffin/render/design_language.py`: `FAMILY_PALETTE`
(every `DesignFamily` with its `ColorFamily` of fill, stroke, emphasis, and ink), the three
neutral inks, and `TABLE_THEME`, a table's tokens as a card of the blue family, every length in
ems of the table's text so the look scales with the type (1 px of the diagram's 15 px text is
0.07 em, the hairline; 1.5 px is 0.1 em, the emphasis weight; the 9.25 px card radius is
0.625 em).  Each format derives its own expression of them at render time, so no bundled
resource carries a family colour of its own (`tests/render/test_design_language.py` checks):

- **PDF.**  `typst_table_tokens()` renders the theme as a Typst dictionary of the Bergfink
  table keys, which the renderer passes as the template's `design-tokens` variable; the template
  joins it onto `cfg` after `base_cfg.typ` and before `user_cfg.typ`, so a user config can still
  override any key.  `default_styles.typ` applies the keys: the rounded, clipped frame
  (`table-radius`, `table-frame-stroke`), the header text (`table-header-ink`,
  `table-header-weight`), the strokes, and the inset.
- **EPUB.**  `table_css()` renders the same theme as stylesheet rules for Pandoc's
  `table`/`thead`/`tbody` markup, written to `design_tokens.css` and loaded after `epub.css`,
  which carries no table styling of its own.

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

Font sizes, faces, and the running text are not part of the mapping: a table is part of the
running text and keeps its face and size.

## Known gaps

- **Faces.**  The diagrams are drawn in IBM Plex Sans and IBM Plex Mono; the PDF's body face is
  Noto Sans with Noto Sans Mono for code (`base_cfg.typ`), and IBM Plex is not installed on the
  development machine.  Until that is decided one way or the other, the diagrams carry their
  own faces and the typeset elements keep the body's.
- **Vertical rules.**  The language parts columns by space, so tables draw none.  A wide table
  with many short columns may want them back: `table-stroke-vertical` is the one key to set.
- **Headerless tables.**  The PDF tints row 0 whether or not it is a header (Bergfink's fill
  keys on the row, as it always did); the EPUB tints only a real `<thead>`.  The EPUB's is the
  truer reading, and the PDF could be brought to it.
- **Reading systems.**  The EPUB's rounded corners rely on `border-radius` and `:last-child`;
  a system without them (the Kindle app is the doubtful one) shows a squarer table.
- **Other styled elements.**  Only tables are mapped so far.  Callouts (gentle-clues, coloured
  by `render/callout_theme.py`), code listings, and pull quotes keep their own styling.
