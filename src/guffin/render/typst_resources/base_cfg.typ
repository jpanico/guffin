// The base configuration for the template
// Don't delete any keys in this dictionary. The template depends on them.

#let cfg = (
  // Metadata
  date: "%today%", // use ISO format like 2022-01-01
  dateformat: "[year]-[month]-[day]",
  authors: (),
  illustrators: (), // supportive contributors, credited "Illustrations by ..." on the title page
  title: "", // plain-text title: PDF /Title metadata and the running-header %title% string machinery
  title-display: none, // rich title content (may carry emphasis), rendered as markup in the running header
  subtitle: "",
  revision: none, // author-declared revision name, rendered below the title on the title page
  publisher: none,
  rights: none,
  keywords: "",
  lang: "en",
  region: "US",
  // Layout
  margin: (x: 2.5cm, top: 3.5cm, bottom: 3.5cm),
  paper: "a4",
  columns: 1,
  color-fg: black,
  color-bg: white,
  // Numbering
  page-numbering: "1",
  page-numbering-both: false,
  number-sections: false,
  section-numbering: "1.1.1.1.1",
  heading-numbering-start-level: 1,
  // Typography
  font: "noto sans",
  heading-font: "noto sans",
  code-font: "noto sans mono",
  header-footer-font: "noto sans",
  // Contrasting body face for callout boxes: a serif set against the sans body so callout
  // content reads as a distinct register at a glance.  Libertinus Serif ships embedded with
  // Typst, so it renders without a system-font dependency.  (Only the callout body uses this;
  // the callout title keeps the ambient `font`.)
  callout-font: "libertinus serif",
  fontsize: 11pt,
  leading: 0.65em,
  spacing: 1.2em,
  justify: true,
  smartquote: true,
  // Per-level heading overrides (size is a ratio multiplied by fontsize)
  h1-size: 1.3,
  h2-size: 1.1,
  h3-size: 1.0,
  h1-weight: "bold",
  h2-weight: "bold",
  h3-weight: "bold",
  h1-style: "normal",
  h2-style: "normal",
  h3-style: "normal",
  // Titlepage
  // Whether the document renders a standalone title page (set from the pandoc `titlepage`
  // variable); without one the title opens the document flow as a heading, and a title-bearing
  // header slot stays empty on the first page so the running title does not double it.
  has-titlepage: false,
  titlepage-rule: 3pt + black,
  titlepage-bg: white,
  titlepage-fg: black,
  titlepage-logo: none,
  titlepage-logo-width: none,
  titlepage-supervisor: none,
  titlepage-provenance: none,
  // Table of contents
  toc: false,
  toc-depth: 6,
  toc-title: "Table of contents",
  toc-own-page: false,
  lof: false,
  lof-title: "List of figures",
  lof-own-page: false,
  lot: false,
  lot-title: "List of tables",
  lot-own-page: false,
  toc-page-numbering: "I",
  // Header and footer
  header-footer-stroke: 1pt + black,
  disable-header: false,
  disable-footer: false,
  header-left: "%title%",
  header-center: none,
  header-right: "%date%",
  footer-left: "none", // the string "none" empties the slot (see footer-left() in default_styles.typ)
  footer-center: none,
  footer-right: "%page%",
  footer-provenance: none,
  // Abstract
  abstract-title: "Abstract",
  abstract: none,
  abstract-own-page: false,
  thanks-title: "Thanks",
  thanks: none,
  // Figures
  figure-prefix: "Fig.",
  table-prefix: "Table",
  listing-prefix: "Listing",
  // Tables
  table-header-bg: luma(200),
  table-striped-bg: luma(230),
  table-stroke-border-x: 1pt + black,
  table-stroke-border-y: 1pt + black,
  table-stroke-header-b: 1pt + black,
  table-stroke-horizontal: 1pt + black,
  table-stroke-vertical: 1pt + black,
  table-inset: 6pt,
  // Other
  listings: false,
  equation-numbering: none,
  glossary: none,
)
