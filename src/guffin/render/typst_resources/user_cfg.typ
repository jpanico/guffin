// these values override base values if provided

#let user_cfg = (
  justify: false, // ragged-right body text; also disables Typst's auto-hyphenation of justified lines
  toc: false,
  number-sections: false,
  section-numbering: "1.", // (top level only)
  heading-numbering-start-level: 2,
  h1-size: 2.0,
  h2-size: 1.6,
  h3-size: 1.3,
  h4-size: 1.2,
  h5-size: 1.1,
  dateformat: "[day].[month].[year]",
  authors: (),
  keywords: "",
  lang: "en",
  region: "US",
  // Tables follow the visual design language (docs/visual-design-language.md): a table is a
  // card — white, framed by a light tinted stroke on a rounded outline — whose header row is a
  // tinted band carrying semibold accent-ink text, and whose rows are parted by hairline rules
  // in the frame's tint.  No vertical rules: columns are parted by their inset, as the
  // language parts everything, by space.  The values are the blue family's tokens.
  table-header-bg: rgb("#EDF2FA"), // blue family: fill
  table-header-ink: rgb("#234279"), // blue family: ink
  table-header-weight: "semibold",
  table-striped-bg: rgb("#F5F5F3"), // neutral family: fill (striped YAML tables only)
  table-stroke-border-x: none,
  table-stroke-border-y: none, // the frame draws the outline
  table-stroke-header-b: 1pt + rgb("#AFC0DC"), // blue family: emphasis stroke
  table-stroke-vertical: none,
  table-stroke-horizontal: 0.75pt + rgb("#C8D5EA"), // blue family: stroke (the hairline)
  table-frame-stroke: 1pt + rgb("#AFC0DC"),
  table-radius: 7pt, // the card radius: 0.625 of the 11pt body size
  table-inset: (x: 10pt, y: 6pt),
)
