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
  // card.  Its table-* values are not set here: the renderer passes them from the language's
  // single source, guffin/render/design_language.py, as the design-tokens variable the template
  // joins before this file, so a table-* key set here would override the language.
)
