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

// set figure styles
#show figure: set block(above: 2em, below: 2em)

#show figure.where(kind: table): set figure.caption(position: top)
#show figure.where(kind: table): set figure(supplement: cfg.table-prefix)
// Left-align tables with the rest of the page; Pandoc emits tables inside a centered
// figure (align(center)[#table(...)]), which this overrides.
#show figure.where(kind: table): set align(left)
// Let a table taller than the page break across page boundaries. Typst figures are
// breakable: false by default, so an over-tall table would otherwise overflow the page
// and render its overflow rows on top of one another.
#show figure.where(kind: table): set block(breakable: true)

#show figure.where(kind: image): set figure.caption(position: bottom)
#show figure.where(kind: image): set figure(supplement: cfg.figure-prefix)

// listings
#show figure.where(kind: raw): set figure.caption(position: bottom)
#show figure.where(kind: raw): set figure(supplement: cfg.listing-prefix)
#show figure.where(kind: raw): set align(left)

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

#show table: set par(justify: false, linebreaks: "optimized")
#show table: set text(hyphenate: true, costs: (hyphenation: 100000%))

// set smart quotes
#set smartquote(enabled: cfg.smartquote)

// reduce code line spacing
#show raw.where(block: true): set text(1em / 0.9)
#show raw: set text(ligatures: true, font: cfg.code-font)

// blockquote styling — gray left border with left padding
#show quote.where(block: true): it => {
  block(
    stroke: (left: 3pt + luma(170)),
    inset: (left: 1em, right: 0em, top: 0.4em, bottom: 0.4em),
    width: 100%,
  )[#it.body]
}

// Fancy block quote (Roam-native [[>]] quotes): a pull-quote treatment — the quotation reads bold at
// 1.5x body size in the quote-font, led by an oversize opening quotation mark, and the attribution
// line(s) are set italic in the attribution-font.  Deliberately carries NO left bar (unlike a plain
// block quote): the oversize mark and large type carry the "quote" signal on their own, which also
// keeps it visually distinct from the plain block quote.  The mark HANGS in a left gutter (placed
// out of flow), and the quotation and attribution share a left edge just to its right — so both
// text lines are left-justified in a column that begins past the mark.  typst_quote.lua marshals
// the quotation and attribution content into a call to this helper.
#let fancy-quote(quote: [], attribution: none) = context {
  // The opening mark: 2.4x the 1.5x quotation text = 3.6x body.  Measured so the text column can be
  // indented by exactly the mark's width plus one space, giving the hanging-mark layout.
  let mark = text(font: cfg.quote-font, weight: "bold", size: 3.6em)[\u{201C}]
  let gutter = measure(mark).width + 0.25em
  block(inset: (left: gutter, top: 0.4em, bottom: 0.4em), width: 100%)[
    // Place the mark in the left gutter, out of the text flow (so short quotes don't inherit its
    // height); dy nudges it down so its ink sits centred-erring-high against the first line.
    #place(left, dx: -gutter, dy: 0.34em)[#mark]
    #block(below: if attribution == none { 0em } else { 0.5em })[
      #set text(font: cfg.quote-font, weight: "bold", size: 1.5em)
      #quote
    ]
    #if attribution != none {
      block[
        #set text(font: cfg.attribution-font, style: "italic")
        #attribution
      ]
    }
  ]
}
