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
  // Tables and callouts follow the design tokens (docs/design-tokens.md): each is a card.
  // Their table-* and callout-* values are not set here: the renderer passes them from the
  // single source, guffin/render/design_language.py, as the design-tokens variables the
  // template joins before this file, so such a key set here would override the tokens.
)
