# Chicago Back-matter

What *The Chicago Manual of Style* (17th edition) says about the back matter of a book, gathered
here as the reference for Guffin's `book` layout, the sibling of
[chicago-front-matter.md](chicago-front-matter.md). Chicago is the base style of the SCFH
project's Style Guide, so where Guffin's layout decisions are silent, this is what governs.

The section numbers below are cited from memory of the 17th edition and should be confirmed
against the manual; the substance is settled. Companion docs:
[notes-design.md](notes-design.md) (the design that applies the notes rules),
[publishing-semantics.md](publishing-semantics.md) (the `element-type::` vocabulary that names
the back-matter divisions an author can tag), and
[chicago-front-matter.md](chicago-front-matter.md) (the other end of the book).


## The sequence of elements (1.4)

The back matter is everything after the text proper: the apparatus a reader consults rather than
reads through. Chicago fixes its order, as it fixes the front matter's, so that a reader who
turns to the back of any book finds the notes before the bibliography and the index last.

| Order | Element | What it is |
|---|---|---|
| 1 | Acknowledgments | When not placed in the front matter (1.42). |
| 2 | Appendix, or appendixes | Material that supports the text but would interrupt it: documents, tables, a long derivation, a case study. |
| 3 | Chronology | When not placed in the front matter. |
| 4 | Abbreviations | When not placed in the front matter; usual in the back when it serves the notes and the bibliography. |
| 5 | Notes | The endnotes of the whole book, when notes are not set at the foot of the page or the end of each chapter. |
| 6 | Glossary | Terms and their definitions, alphabetically. |
| 7 | Bibliography, or references | The works cited or consulted. |
| 8 | List of contributors | In a multi-author volume. |
| 9 | Illustration credits | When not given in the captions or on the copyright page. |
| 10 | Index, or indexes | Always last of the apparatus. |

Two further pages may follow the index, outside the apparatus: a **biographical note** about the
author (1.66), when it is not on the jacket or the copyright page, and a **colophon** (1.67), a
statement of the book's production, the typeface, paper, designer, and printer, on the last page.

What is *not* back matter: a **conclusion**, an **epilogue**, or an **afterword** (1.53–1.54).
These close the text and belong to it, numbered and paginated as its last division. An afterword
is sometimes by another hand, which is why it is often mistaken for an appendix, but Chicago keeps
it with the text.


## Page numbering and running heads (1.5–1.16)

The arabic numbering of the text continues through the back matter without a break; there is no
second sequence as there is for the front matter. Every page counts and, unlike the display pages
of the front matter, nearly every page shows its number: the only unnumbered pages at the back
are blanks and the colophon.

Each major element begins on a **recto**, as the text's chapters do: the first appendix, the
notes, the glossary, the bibliography, and the index each open on a right-hand page. Publishers
short of pages let later appendixes, the glossary, or the credits open on a verso; the index
begins on a recto whatever the economy.

Running heads name the element: *Appendix A* on the verso and the appendix's title on the recto,
*Glossary*, *Bibliography*, *Index*. The notes are the exception and the one place Chicago spends
a rule (1.15): because a reader arrives at the notes from a page of the text, their running heads
give the **range of text pages** whose notes appear below, *Notes to Pages 112–118*, not the
chapter. It is the device that makes unnumbered, invisible endnotes findable.


## The elements

### Appendixes (1.57–1.58)

- One appendix is titled *Appendix*; several are lettered, *Appendix A*, *Appendix B*, and each
  has a title of its own.
- An appendix is treated as a chapter in its display: the same heading style, a recto opening,
  running heads, and an entry in the contents. It may be set in smaller type than the text when
  it is reference material, and it may carry its own notes.
- Appendixes belonging to one chapter may instead be placed at the end of that chapter, before
  the next; the whole-book appendix in the back matter is the default.

### Notes (1.60; 14.43–14.47)

- The section is headed *Notes*. Within it the notes are grouped by chapter under subheads that
  give the chapter number and title, *Chapter 3: The Lives of Programs*, so that a reader can
  find a chapter's notes without the index; the numbering of the notes restarts with each chapter.
- The running heads carry the text pages, as above. In a book whose notes are keyed to phrases
  rather than numbered, each note opens with the page number and the phrase it comments on, set
  off from the note's text; the page number is the locator and the phrase the key.
- Notes to the front matter (a preface, an introduction) come first, under their element's name;
  notes to an appendix come last.
- The source of an epigraph is not given in the notes; it stands in the source line under the
  epigraph (13.36). A separate list, *Sources of Epigraphs* or *Epigraph Credits*, is a
  publisher's option, placed with the credits.

### Glossary (1.61)

- Alphabetical by term; each entry the term, set in italics or bold, followed by its definition
  in roman, usually without a terminal period when the definition is a fragment.
- Placed after the notes and before the bibliography, so that a term met in a note can still be
  looked up ahead of the works that use it.

### Bibliography or references (1.62; chapter 14)

- *Bibliography* is Chicago's name for the list in the notes-and-bibliography system of citation;
  *References* or *Works Cited* in the author-date system. One list, alphabetical by author;
  divisions by kind (primary and secondary sources, archives) only when the reader is served by
  them.
- It follows the notes and the glossary and precedes the index.

### Illustration credits (1.64; 3.29–3.33)

- Credits that are not given in the captions are gathered in a list, after the bibliography and
  before the index, or placed on the copyright page when they are few.

### Index (1.65; chapter 16)

- The last of the apparatus, opening on a recto, usually set in two columns in a size below the
  text. A book may carry more than one (names and subjects), each titled.
- Chicago's indexing rules are a chapter of their own and are not summarized here; Guffin
  produces no index.

### Biographical note and colophon (1.66–1.67)

- A short note on the author, when not on the jacket or the copyright page, takes the last page
  before the colophon, or the last page of all.
- The colophon, Chicago's sense of the word, describes the making of the book: typeface, its
  designer, the paper, the printer and binder. It is optional, unnumbered, and the final page.
  Guffin's own *colophon* line, the software provenance and content revision it stamps on an
  export, is a different thing that happens to share the name and the position.


## What it means for Guffin's book layout

- **The vocabulary covers the elements an author tags.** `element-type::` names `appendix`,
  `endnotes`, `glossary`, `bibliography`, `index`, `about-the-author`, and `colophon`, each
  carrying `Matter.BACK`, and `afterword`, which Guffin also files as back matter. Chicago keeps
  an afterword with the text, as it keeps a conclusion and an epilogue, which the vocabulary does
  file as body matter; whether `afterword` should follow them is a decision not yet taken. A
  heading tagged with any of these is left unnumbered, since back matter stands outside the
  body's numbering, and stamped with its `epub:type`; an authored `matter::` tag can move a
  bespoke section into the back matter without naming its kind.
- **The sequence is the author's.** Guffin renders back-matter sections in the order they appear
  on the export root; it does not reorder them to Chicago's sequence. In a parts book, a root-level
  back-matter section is promoted to part level so that no contents list nests it under the last
  part (`promote_non_body_sections`), which is the one structural rule it enforces.
- **Notes.** A `book` keeps invisible endnotes gathered into an author-created `endnotes` section
  ([notes-design.md](notes-design.md)). The PDF groups them by chapter under generated subheads
  that repeat the chapter's title, as Chicago's subheads do, and opens each entry with the page
  number of the passage and its lead-in, Chicago's locator and key for unnumbered notes. The
  EPUB and the Markdown group by chapter and then by section, and link each entry back to its
  passage. The *Notes to Pages* running head is not produced; the per-entry page locator stands in
  for it. The SCFH decision of 2026-10-14 puts the complete notes in the digital editions and the
  public repo, and shortened notes in print.
- **Appendixes.** The one appendix Guffin generates holds the PDF assets an author places there
  (`pdf-render:: appendix-native` / `appendix-image`): a single section titled *Appendix*, one
  subsection per PDF, with an internal link from each embed, emitted at level 1 so that it is a
  sibling of a parts book's parts, and unnumbered. An author-tagged `appendix` heading is a
  section like any other back-matter section; Guffin does not letter appendixes.
- **Colophon.** Guffin's provenance colophon rides the title page when one is emitted and the
  page footer otherwise in the PDF, and the end of the last document in the EPUB; an authored
  `element-type:: colophon` section is independent of it, and a book may have both.
- **Pagination.** Guffin's `book` layout opens every chapter and part on a new page, and the
  back-matter sections with them, but it knows nothing of rectos and versos: a section opens on
  the next page, whichever side it falls on. Blank versos before a recto opening, and running
  heads that name the element, are design work not yet done.
- **Not produced.** No index, no glossary or bibliography formatting beyond the heading, no list
  of illustration credits, no *Sources of Epigraphs*. Each is a possible element; the SCFH
  `[[Epigrams]]` page already carries the citation under every epigraph that such a list would be
  made from.
