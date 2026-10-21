// for markdown hr
#let horizontalrule = line(start: (25%, 0%), end: (75%, 0%))

// definition list styling
#show terms: it => {
  it
    .children
    .map(child => [
      #strong[#child.term]
      #block(inset: (left: 1.5em))[#child.description]
    ])
    .join()
}

// author parsing
#let authors_oneline = cfg.authors.map(a => a.name).join(", ")
#if authors_oneline == none {
  authors_oneline = ""
}
#let authors_name_array = cfg.authors.map(a => a.name)

#let disable-header = cfg.disable-header
#let disable-footer = cfg.disable-footer
#let font = cfg.font
#let header-footer-font = cfg.header-footer-font

#let replace_header_content(content) = {
  if content != none {
    if content == "%page%" {
      let both = context {
        page
          .numbering
          .clusters()
          .filter(c => (
            c
              in (
                "1",
                "a",
                "A",
                "i",
                "I",
                "α",
                "Α",
                "*",
                "א",
                "一",
                "壹",
                "あ",
                "い",
                "ア",
                "イ",
                "ㄱ",
                "가",
                "\u{0661}",
                "\u{06F1}",
                "\u{0967}",
                "\u{09E7}",
                "\u{0995}",
                "①",
                "⓵",
              )
          ))
          .len()
        if both >= 2 {
          return context counter(page).display(page.numbering, both: true)
        }
      }

      return context counter(page).display(page.numbering)
    }

    let replaced = content
      .replace("%date%", display_date(cfg.date, cfg.dateformat))
      .replace("%author%", authors_oneline)
    // The title renders as content so a portion carrying emphasis (e.g. a bold word in the page
    // name) shows as real markup rather than plain text.  Split on the %title% placeholder and
    // interleave the rich title content; slots without %title% stay plain strings.  A document with
    // no rich title (title-display unset) falls back to the plain title string.
    if replaced.contains("%title%") {
      let title-content = if cfg.title-display != none { cfg.title-display } else { cfg.title }
      return replaced.split("%title%").map(part => [#part]).join(title-content)
    }
    return replaced
  }
}

// Which header slots reference the document title, recorded from the raw config strings before
// the placeholder replacement below rewrites them.
#let header-slot-has-title = (
  left: type(cfg.header-left) == str and cfg.header-left.contains("%title%"),
  center: type(cfg.header-center) == str and cfg.header-center.contains("%title%"),
  right: type(cfg.header-right) == str and cfg.header-right.contains("%title%"),
)

#(cfg.header-left = replace_header_content(cfg.header-left))
#(cfg.header-center = replace_header_content(cfg.header-center))
#(cfg.header-right = replace_header_content(cfg.header-right))
#(cfg.footer-left = replace_header_content(cfg.footer-left))
#(cfg.footer-center = replace_header_content(cfg.footer-center))
#(cfg.footer-right = replace_header_content(cfg.footer-right))


// The right header cell: the authored revision name (when set) replaces the configured right
// content (the publication date by default) — the more version-specific fact wins the slot.
#let header-right-cell() = {
  if cfg.revision != none [
    #text(style: "italic")[revision: #cfg.revision]
  ] else {
    cfg.header-right
  }
}

// Define a helper for the header
#let make-header() = context {
  // Without a title page the title opens the document flow as a heading, so on the first page a
  // title-bearing slot stays empty — the running title would double it, one directly below the
  // other.  Later pages run the full header, and a document with a title page is unaffected.
  let suppress-title = cfg.has-titlepage != true and counter(page).get().first() == 1
  if disable-header != true [
    #set text(font: header-footer-font)
    #grid(
      columns: (auto, 1fr, auto),
      align: (left, center, right),
      if suppress-title and header-slot-has-title.left { none } else { cfg.header-left },
      if suppress-title and header-slot-has-title.center { none } else { cfg.header-center },
      if suppress-title and header-slot-has-title.right { none } else { header-right-cell() },
    )
    #v(-par.spacing + 0.5em)
    #line(length: 100%, stroke: cfg.header-footer-stroke)
  ] else []
}

// Define a helper for the footer
#let footer-left() = {
  let fl = cfg.footer-left

  if lower(fl) == "none" {
    return none
  } else {
    return fl
  }
}

#let footer-right() = {
  let fr = cfg.footer-right

  if lower(fr) == "none" {
    return none
  } else {
    return fr
  }
}

#let make-footer() = context {
  if disable-footer != true [
    #set text(font: header-footer-font)
    #line(length: 100%, stroke: cfg.header-footer-stroke)
    #v(-par.spacing + 0.5em)
    #grid(
      columns: (auto, 1fr, auto),
      align: (left, center, right),
      footer-left(), cfg.footer-center, footer-right(),
    )
    // Provenance line, below the normal footer row when supplied.
    #if cfg.footer-provenance != none [
      #v(0.2em)
      #align(center, text(size: 0.7em, fill: gray)[#cfg.footer-provenance])
    ]
  ] else []
}

// setting pdf meta data
// document(date:) takes datetime | auto | none; a reduced-precision date string has no
// datetime representation, so the PDF metadata date is omitted rather than fabricated.
#set document(
  title: cfg.title,
  keywords: cfg.keywords,
  date: if type(cfg.date) == datetime { cfg.date } else { none },
  author: authors_name_array,
)

#let margin = cfg.margin
#if disable-header == true {
  margin = (x: margin.x, top: margin.top - 3em, bottom: margin.bottom)
}

#if disable-footer == true {
  margin = (x: margin.x, top: margin.top, bottom: margin.bottom - 3em)
}

#set page(
  paper: cfg.paper,
  margin: margin,
  numbering: cfg.page-numbering,
)

#let leading = cfg.leading
#set par(
  justify: cfg.justify,
  leading: leading,
  spacing: cfg.spacing,
)

#let fontsize = cfg.fontsize

#set text(
  lang: cfg.lang,
  region: cfg.region,
  font: font,
  size: fontsize,
)

// set heading styles
#let numbering-fn = none
#if cfg.number-sections {
  let start = cfg.heading-numbering-start-level
  let fmt = cfg.section-numbering
  if start <= 1 {
    numbering-fn = fmt
  } else {
    numbering-fn = (..args) => {
      let nums = args.pos()
      if nums.len() < start {
        none
      } else {
        numbering(fmt, ..nums.slice(start - 1))
      }
    }
  }
}

#set heading(numbering: numbering-fn)

#show heading: set text(font: cfg.heading-font)

#show heading.where(level: 1): set text(fontsize * cfg.h1-size, weight: cfg.h1-weight, style: cfg.h1-style)
#show heading.where(level: 1): set block(above: 2.65em, below: 1.75em)

#show heading.where(level: 2): set text(fontsize * cfg.h2-size, weight: cfg.h2-weight, style: cfg.h2-style)
#show heading.where(level: 2): set block(above: 2em, below: 1.375em)

#show heading.where(level: 3): set text(fontsize * cfg.h3-size, weight: cfg.h3-weight, style: cfg.h3-style)
#show heading.where(level: 3): set block(above: 2em, below: 1em)

#show heading.where(level: 4): set text(fontsize * cfg.h4-size, weight: cfg.h4-weight, style: cfg.h4-style)
#show heading.where(level: 4): set block(above: 2em, below: 1em)

#show heading.where(level: 5): set text(fontsize * cfg.h5-size, weight: cfg.h5-weight, style: cfg.h5-style)
#show heading.where(level: 5): set block(above: 2em, below: 1em)

// set figure styles
#show figure: set block(above: 2em, below: 2em)
// A float's number is written into its caption by the renderer (one number in every format), so
// Typst's own figure numbering, and the supplement it would prefix, are turned off.
#show figure: set figure(numbering: none)

#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set figure(supplement: cfg.table-prefix)
// Left-align tables with the rest of the page.  Pandoc emits every table inside a figure as
// align(center)[#table(...)], and a set rule cannot override that explicit alignment, so two rules
// share the work: the set rule places the figure at the left margin, and the show rule unwraps the
// centering call around the table itself.  Without the unwrapping a captionless table still looks
// left-aligned (its figure is only as wide as the table), but a caption widens the figure to the
// caption's width and the table is centered beneath it.  Only an align whose body is the table is
// unwrapped, so an alignment authored inside a cell is kept.  (Typst 0.14 cannot select the
// centering call with align.where(alignment: center), hence the body test.)
#show figure.where(kind: table): set align(left)
#show figure.where(kind: table): it => {
  show align: inner => if inner.body.func() == table { inner.body } else { inner }
  it
}
// Let a table taller than the page break across page boundaries. Typst figures are
// breakable: false by default, so an over-tall table would otherwise overflow the page
// and render its overflow rows on top of one another.
#show figure.where(kind: table): set block(breakable: true)

#show figure.where(kind: image): set figure.caption(position: bottom)
#show figure.where(kind: image): set figure(supplement: cfg.figure-prefix)

// Cap every image at the width of its container.  An image keeps the width its source gave it (a
// pixel width becomes inches at 96 px/in), which can exceed the text column, and Typst never
// shrinks an image of a set width to fit, so it would run into the margins.  An image that fits is
// left as it is; a wider one is scaled down to the container's width, its height following, and
// the scaled image takes only the space it shows (reflow).  The set width is read off the element
// rather than measured, since measure reports the width already clipped to the container; an image
// of auto width is fitted by Typst itself.
#show image: it => {
  if it.width == auto {
    return it
  }
  layout(size => {
    let width = it.width + 0%
    let natural = width.ratio * size.width + width.length.to-absolute()
    if natural <= size.width {
      it
    } else {
      let factor = size.width / natural * 100%
      scale(x: factor, y: factor, reflow: true, it)
    }
  })
}

// The size of the text block on the current page: the page less its margins.  Call it in context.
#let text-block-size() = {
  let margin = page.margin
  let side(value, extent) = {
    let length = value + 0%
    length.ratio * extent + length.length.to-absolute()
  }
  let sides = if margin == auto {
    let default = 2.5 / 21 * calc.min(page.width, page.height)
    (top: default, bottom: default, left: default, right: default)
  } else if type(margin) == dictionary {
    (
      top: side(margin.at("top", default: 0pt), page.height),
      bottom: side(margin.at("bottom", default: 0pt), page.height),
      left: side(margin.at("left", default: margin.at("inside", default: 0pt)), page.width),
      right: side(margin.at("right", default: margin.at("outside", default: 0pt)), page.width),
    )
  } else {
    let vertical = side(margin, page.height)
    let horizontal = side(margin, page.width)
    (top: vertical, bottom: vertical, left: horizontal, right: horizontal)
  }
  (width: page.width - sides.left - sides.right, height: page.height - sides.top - sides.bottom)
}

// Keep a lead-in on the page of the image it introduces, when the two fit on a page together.
// The lead-in is set as a sticky block, so Typst never breaks the page between it and the image,
// unless the pair is taller than the text block: then no page could hold both, and a sticky
// lead-in would only be moved to a page of its own ahead of the image, leaving the page it was on
// short.  It is set as an ordinary block instead, staying where it falls.  `next` is a copy of the
// block that follows, measured and never placed.  (The context, unlike a layout call, leaves the
// sticky block in the flow, where its stickiness takes effect.)
#let keep-with-next(next: none, lead) = context {
  let size = text-block-size()
  let together = measure(block(width: size.width, lead + parbreak() + next)).height
  block(sticky: together <= size.height, lead)
}

// Fit an image figure, caption and all, within the text block.  A figure cannot break across
// pages, so one taller than the text block overflows its page, its caption running into the
// footer.  The images in such a figure are scaled down by the overflow, their width following, so
// the figure fits; the caption keeps its size.  The figure itself is returned, so its label, and
// every reference and list entry pointing at it, stay with it.  Each image is measured at its
// natural size (a measure with no height bound, the width cap applied) and laid out in a box of
// exactly that size before it is scaled: scaled bare, an image of auto size would fit itself to
// the region the scale enlarges for it and come out no smaller.
#show figure.where(kind: image): it => context {
  let size = text-block-size()
  let overflow = measure(block(width: size.width, it)).height - size.height
  if overflow <= 0pt {
    return it
  }
  let body = measure(block(width: size.width, it.body)).height
  let factor = calc.max(0.0, (body - overflow) / body) * 100%
  show image: inner => {
    let natural = measure(inner, width: size.width)
    scale(x: factor, y: factor, reflow: true, box(width: natural.width, height: natural.height, inner))
  }
  it
}

// listings
#show figure.where(kind: raw): set figure.caption(position: bottom)
#show figure.where(kind: raw): set figure(supplement: cfg.listing-prefix)
#show figure.where(kind: raw): set align(left)
// Let a listing longer than the page break across page boundaries, as a table may (above): a
// figure is unbreakable by default, so a long listing float would otherwise overflow its page and
// pile its last lines onto its caption.  The caption follows the listing's last part.
#show figure.where(kind: raw): set block(breakable: true)

// set captions to left
#show figure.caption: set align(left)

// indent lists
#show list: set list(indent: 6pt)
#show enum: set enum(indent: 6pt)

// table styling
#let table-stroke = (x, y) => (
  left: if x == 0 { cfg.table-stroke-border-x } else { cfg.table-stroke-vertical },
  right: cfg.table-stroke-border-x,
  top: if y == 0 { cfg.table-stroke-border-y } else if y == 1 { cfg.table-stroke-header-b } else {
    cfg.table-stroke-horizontal
  },
  bottom: cfg.table-stroke-border-y,
  x: cfg.table-stroke-vertical,
  y: cfg.table-stroke-horizontal,
)

// fill for striped tables
#let striped = (x, y) => {
  if y == 0 {
    cfg.table-header-bg
  } else if calc.even(y) and y > 1 {
    cfg.table-striped-bg
  } else {
    none
  }
}

#let table-fill = (x, y) => {
  if y == 0 {
    cfg.table-header-bg
  } else {
    none
  }
}

#set table(
  stroke: table-stroke,
  inset: cfg.table-inset,
  fill: table-fill,
)

// A horizontal rule placed in the table (Pandoc emits one under the header row) takes the
// header's bottom stroke, so it never draws over the configured strokes in Typst's default black.
#set table.hline(stroke: cfg.table-stroke-header-b)

// The header row's text (row 0, the row the header fill also keys on).  Both are show-set rules,
// so a table with no header can set row 0 back in the surrounding type (below).
#show table.cell.where(y: 0): set text(weight: cfg.table-header-weight)
#show table.cell.where(y: 0): set text(fill: cfg.table-header-ink) if cfg.table-header-ink != auto

// A callout box: a card — white, framed on a rounded outline — whose title band carries the
// icon and the title in the kind's ink, with the body beneath, parted from the band by the
// frame stroke; a callout without a body is the band alone.  `kind` picks the colours from
// cfg.callout-colors; `icon` is the SVG source as a string, drawn in currentColor, which is
// replaced by the ink here since an image inherits no text colour.  The band is sticky, so a
// box that breaks across pages never leaves its band stranded at a page foot.
#let callout(kind: "note", title: none, icon: none, with-body: true, body) = {
  let colors = cfg.callout-colors.at(kind, default: cfg.callout-default-colors)
  let frame = cfg.callout-frame-width + colors.frame
  let title-content = if title == none { none } else {
    text(fill: colors.ink, weight: cfg.callout-title-weight, title)
  }
  let icon-content = if icon == none { none } else {
    box(height: cfg.callout-icon-size, image(bytes(icon.replace("currentColor", colors.ink.to-hex())), format: "svg"))
  }
  let band = block(
    sticky: true,
    width: 100%,
    fill: colors.fill,
    inset: cfg.callout-header-inset,
    below: 0pt,
    stroke: if with-body { (bottom: frame) } else { none },
    if icon-content == none { title-content } else if title-content == none { icon-content } else {
      grid(columns: (auto, auto), align: (horizon, left + horizon), gutter: 0.6em, icon-content, title-content)
    },
  )
  block(
    width: 100%,
    radius: cfg.callout-radius,
    clip: true,
    stroke: frame,
    fill: white,
    breakable: true,
    above: 1em,
    below: 1em,
    {
      set par(first-line-indent: 0pt, justify: false)
      band
      if with-body {
        block(width: 100%, inset: cfg.callout-body-inset, below: 0pt, {
          set text(font: cfg.callout-font)
          body
        })
      }
    },
  )
}

// The frame: the whole table in a block clipped to the configured corner radius and stroked
// around that outline, so the header fill's corners are rounded with it.  Breakable, like the
// figure holding it, so a tall table still runs across pages, each fragment framed.
#show table: it => block(
  radius: cfg.table-radius,
  clip: true,
  stroke: cfg.table-frame-stroke,
  breakable: true,
  it,
)

// A table with no header row (no table.header among its children) sets row 0 as an ordinary row.
// The rules above key the header's fill, the rule beneath it, and its type on row 0, and a set rule
// inside a table's own show rule no longer reaches that table, so the table is rebuilt: no fill,
// the ordinary rule between rows 0 and 1, and row 0 in the surrounding type.  Only a table on the
// default fill is rebuilt, so one that sets its own fill keeps it (the rebuilt table, on no fill,
// is left alone in turn); a labelled table is left as it is, since the rebuilt one could not carry
// the label.
#let headless-table-stroke = (x, y) => {
  let stroke = table-stroke(x, y)
  if y == 1 { stroke + (top: cfg.table-stroke-horizontal) } else { stroke }
}
#show table: it => {
  if it.fill != table-fill or it.has("label") or it.children.any(child => child.func() == table.header) {
    return it
  }
  let fields = it.fields()
  let children = fields.remove("children")
  let stroke = if it.stroke == table-stroke { headless-table-stroke } else { it.stroke }
  context {
    let ink = text.fill
    let weight = text.weight
    show table.cell.where(y: 0): set text(fill: ink, weight: weight)
    table(..fields, fill: none, stroke: stroke, ..children)
  }
}

// Row splitting across pages is governed per cell in Typst (a cell in an auto-height row is
// breakable unless told otherwise), so the table-level policy is applied to every cell.
#set table.cell(breakable: cfg.table-rows-breakable)

#show table: set par(justify: false, linebreaks: "optimized")
#show table: set text(hyphenate: true, costs: (hyphenation: 100000%))

// set smart quotes
#set smartquote(enabled: cfg.smartquote)

// reduce code line spacing
#show raw.where(block: true): set text(1em / 0.9)
#show raw: set text(ligatures: true, font: cfg.code-font)

// additional highlighting grammars beyond Typst's bundled syntect set (e.g. fixed-form
// FORTRAN); absolute paths supplied by the renderer via the code-syntaxes variable
#set raw(syntaxes: cfg.code-syntaxes)

// blockquote styling — gray left border with left padding
#show quote.where(block: true): it => {
  block(
    stroke: (left: 3pt + luma(170)),
    inset: (left: 1em, right: 0em, top: 0.4em, bottom: 0.4em),
    width: 100%,
  )[#it.body]
}

// Pull quote (Roam [[>]] [[!QUOTE]]): a passage of the work's own text promoted for display — the
// quotation reads at cfg.quote-size (default 1.2x body size) and cfg.quote-weight (default bold) in
// the quote-font, led by an oversize opening quotation mark.  It carries no attribution: its source
// is the work itself.  Deliberately carries NO left bar (unlike a plain block quote): the oversize
// mark and large type carry the "quote" signal on their own, which also keeps it visually distinct
// from the plain block quote.  The mark HANGS in a left gutter (placed out of flow), and the
// quotation is left-justified in a column that begins just past it.  typst_quote.lua marshals the
// quotation into a call to this helper.
#let fancy-quote(quote: []) = context {
  // The opening mark: 2.4x the quotation text (2.88x body at the default quote-size of 1.2), always
  // bold whatever the quote-weight.  Measured so the text column can be indented by exactly the
  // mark's width plus one space, giving the hanging-mark layout.
  let mark = text(font: cfg.quote-font, weight: "bold", size: 2.4 * cfg.quote-size * 1em)[\u{201C}]
  let gutter = measure(mark).width + 0.25em
  block(inset: (left: gutter, top: 0.4em, bottom: 0.4em), width: 100%)[
    // Place the mark in the left gutter, out of the text flow (so short quotes don't inherit its
    // height); dy nudges it down so its ink sits centred-erring-high against the first line.  The
    // nudge was tuned at quote-size 1.5 and scales with it.
    #place(left, dx: -gutter, dy: 0.34em * cfg.quote-size / 1.5)[#mark]
    #block(below: 0em)[
      #set text(font: cfg.quote-font, weight: cfg.quote-weight, size: cfg.quote-size * 1em)
      #quote
    ]
  ]
}

// Epigraph (Roam [[>]] [[!EPIGRAPH]]): a quotation set at the opening of a work, part, or chapter.
// It takes the alignment of the headings above it, which this template sets flush left: the
// quotation starts at the left margin, its lines ragged, wrapping at cfg.epigraph-width of the text
// block, at cfg.epigraph-size of the body size with cfg.epigraph-leading between its lines, in
// cfg.epigraph-style.  The attribution sits beneath
// it, upright, flush right against the quotation's own longest line rather than the page margin, so
// the source stays with a short quotation instead of drifting to the far edge: the epigraph is
// measured and set in a block exactly as wide as its widest line (quotation or attribution), capped
// at the wrap width.  No rule or indent, unlike a block quote: the type and the space around it
// carry the signal.  typst_quote.lua marshals the quotation and attribution into a call to this
// helper.
#let epigraph(quote: [], attribution: none) = block(width: 100%, above: 1.5em, below: 2em, {
  set par(justify: false, leading: cfg.epigraph-leading)
  set text(size: cfg.epigraph-size * 1em)
  layout(region => {
    let limit = cfg.epigraph-width * region.width
    let body = text(style: cfg.epigraph-style, quote)
    // measure with a width constrains the layout, so a wrapping quotation reports its widest line.
    let quote-width = measure(body, width: limit).width
    let source-width = if attribution == none { 0pt } else { measure(attribution, width: limit).width }
    block(width: calc.max(quote-width, source-width), {
      body
      if attribution != none {
        block(above: 0.8em, width: 100%, align(right, attribution))
      }
    })
  })
})

// Alternatives (export-roam-tree --render-alternatives): a block's selected wording and its
// alternative wordings, rendered as one group.  A thin dashed rail binds the group —
// deliberately unlike the block quote's solid 3pt bar — and a radio marker leads each wording,
// filled for the selected one and hollow for each alternative, so which wording is in force never
// rests on colour alone.  The selected wording reads as ordinary body text; each alternative is
// muted and set a touch smaller, and never italic, so emphasis inside it survives.
// typst_alternatives.lua marshals a group in flow into alternatives-group; typst_bullet.lua lays
// out a list holding a versioned item as a grid built from the same pieces.
#let alternative-rail = (paint: luma(185), thickness: 0.8pt, dash: (2pt, 2pt))
#let alternative-muted = luma(115)

// The radio marker, drawn from primitives (no font glyph, so no tofu): a ring with a centre dot
// for the selected wording, a muted bare ring for an alternative.
#let alternative-marker(selected) = box(baseline: 0.12em, {
  let diameter = 0.62em
  if selected {
    circle(radius: diameter / 2, stroke: 0.7pt + black, inset: 0pt,
      align(center + horizon, circle(radius: diameter / 4.2, fill: black, stroke: none)))
  } else {
    circle(radius: diameter / 2, stroke: 0.7pt + alternative-muted)
  }
})

// An alternative wording's text treatment.
#let alternative-wording(body) = text(size: 0.93em, fill: alternative-muted, body)

// The space between a group's wordings: a line's worth for wordings of running text, and wider for
// display wordings such as epigraphs, which set their own space around themselves in the flow but
// lose it inside the group's grid, where nothing would separate one wording's source line from the
// next wording's quotation.
#let alternative-gutter = 0.55em
#let alternative-display-gutter = 1.1em

// A group in the document flow: the selected wording, then each alternative, stacked, each led
// by its marker.  With hang (a group in the body's own flow), the rail and markers hang into the
// left margin so the selected wording keeps the body's left edge; without it (a group nested in a
// list item or another container, whose margin belongs to that container), the whole group sits
// inside the text column.  gutter is the space between wordings.
#let alternatives-group(hang: true, gutter: alternative-gutter, selected, ..alternatives) = {
  let group = block(
    width: 100%,
    stroke: (left: alternative-rail),
    inset: (left: 0.35em, y: 0.15em),
    grid(
      columns: (1.25em, 1fr),
      row-gutter: gutter,
      alternative-marker(true), selected,
      ..alternatives.pos().map(wording => (alternative-marker(false), alternative-wording(wording))).flatten(),
    ),
  )
  if hang { pad(left: -1.6em, group) } else { group }
}
