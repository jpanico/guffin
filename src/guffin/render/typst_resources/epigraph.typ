// The book epigraph: a page of its own in the front matter, after the title page and before the
// contents, per Chicago (17th ed., 1.36; see docs/chicago-front-matter.md).  The renderer lifts an
// epigraph authored above the document's first heading out of the body and passes it as the
// book-epigraph variable, rendered through the same #epigraph helper as a chapter epigraph, so the
// page shows nothing but the epigraph: no running head, no footer, no printed page number, the
// epigraph set a cfg.epigraph-page-sink share of the page down from the top, at the text block's
// left margin.  The page ends with a break, so the contents open on a fresh page.
#if cfg.book-epigraph != none {
  page(numbering: none, header: none, footer: none)[
    #v(cfg.epigraph-page-sink * 100%)
    #cfg.book-epigraph
  ]
}
