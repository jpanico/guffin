# Chicago Front-matter

What *The Chicago Manual of Style* (17th edition) says about the front matter of a book, and in
particular about a book's epigraph, gathered here as the reference for Guffin's `book` layout.
Chicago is the base style of the SCFH project's Style Guide, so where Guffin's layout decisions
are silent, this is what governs.

The section numbers below are cited from memory of the 17th edition and should be confirmed
against the manual; the substance is settled. Companion docs:
[book-epigraph-design.md](book-epigraph-design.md) (the design that applies these rules to the
epigraph page), [publishing-semantics.md](publishing-semantics.md) (the `element-type::`
vocabulary that names the front-matter divisions an author can tag), and
[chicago-back-matter.md](chicago-back-matter.md) (the other end of the book).


## The sequence of elements (1.4)

The front matter is a fixed sequence of pages before the text proper. None of it depends on the
book's content; it is the furniture every printed book carries, in the order readers expect.

| Order | Element | What it is |
|---|---|---|
| 1 | Half title | A page carrying only the book's main title. It opens the book. |
| 2 | Series title, frontispiece, or blank | The back of the half title: the series name if the book belongs to one, or an illustration facing the title page, or nothing. |
| 3 | Title page | Title, subtitle, author, publisher. |
| 4 | Copyright page | The back of the title page: copyright notice, publisher's address, edition and printing history, ISBN, cataloging data. |
| 5 | Dedication | The "To …" page, when the book has one. |
| 6 | Epigraph | The book's epigraph, when it has one. |
| 7 | Contents | The table of contents. |
| 8 | Lists of illustrations and tables | When the book has them. |
| 9 | Foreword | By someone other than the author. |
| 10 | Preface | By the author. |
| 11 | Acknowledgments | When not part of the preface. |
| 12 | Introduction | Only when it is not part of the text proper. |
| 13 | Abbreviations, chronology | When the reader needs them before the text. |

The text proper follows, opening on a recto, often after a second half title.


## Recto and verso

A printed book's pages come in pairs. The right-hand page of an open book is the **recto** and
always carries an odd number; the left-hand page is the **verso** and carries an even number. The
major elements of the front matter begin on a recto, because that is where the eye lands when a
page is turned: the half title, the title page, the dedication, and the contents all open on
rectos. The versos between them take whatever belongs on the back of each: the series title behind
the half title, the copyright notice behind the title page, and, when there is a dedication, the
epigraph behind it. The epigraph is the one element that regularly sits on a verso.

The words are Latin: *recto* is short for *recto folio*, "on the right leaf", and *verso* for
*verso folio*, "on the turned leaf". They date from when books were foliated rather than
paginated, each leaf bearing one number and a reference naming its side (12r, 12v), and they
survived when every page got its own number.


## Page numbering (1.5–1.7)

Front matter is numbered in lowercase roman numerals, i, ii, iii, …, separately from the text,
which starts over at arabic 1. Every page is counted; only some show their number. The **display
pages** (half title, title page, copyright page, dedication, epigraph, and blank pages) carry no
printed number and no running head (1.11); they are counted all the same.

Counting from the half title gives the standard scheme:

| Page | Side | Element |
|---|---|---|
| i | recto | half title |
| ii | verso | series title, frontispiece, or blank |
| iii | recto | title page |
| iv | verso | copyright page |
| v | recto | dedication |
| vi | verso | epigraph (or blank) |
| vii | recto | contents |

The contents list only what follows them (1.38): the dedication and epigraph, which precede the
contents, are never listed there.


## The book epigraph

### Placement (1.36)

- The epigraph goes in the front matter after the dedication and before the contents.
- It is the one display element Chicago routinely places on a **verso**. The manual's outline gives
  its page as "v or vi": **with a dedication** on page v, the epigraph goes on vi, the back of the
  dedication's leaf, and the contents open on vii, so the reader meets the epigraph and the
  contents as one spread. Setting the epigraph on the next recto instead, vii, with the contents
  moved to ix, is a designer's choice some publishers make, not the manual's default. Chicago also
  allows the dedication and the epigraph to share one page when space is short.
- **Without a dedication**, the epigraph takes the dedication's place, page v, the first recto after
  the copyright page, with vi blank and the contents beginning on vii.
- The epigraph never goes on the title page or the copyright page.
- One alternative position exists (1.46): the verso of a **second half title**, the page facing the
  first page of the text, in a book whose front matter is long.

### Display (1.6–1.7, 1.11)

- The epigraph page is a display page: no running head, no printed page number, though it counts
  in the roman numbering.
- When the epigraph has a recto to itself (page v, no dedication), the verso behind it is blank and
  the contents begin on the next recto.
- It is not listed in the contents.

### The quotation and its source (13.36–13.37)

- An epigraph is set **without quotation marks**.
- Its **source** goes on the line below, usually led by an em dash. Only the author's name, or the
  name and the title of the work, is given; a full citation is not usual.
- Because the source line identifies it, an epigraph takes **no note number**, and its source is
  not repeated in the notes or the bibliography.
- It is otherwise treated as a quotation: wording and punctuation follow the original, with the
  usual silent changes permitted (an initial capital adjusted, a final period added). An omission
  within it takes an ellipsis; an epigraph may begin mid-sentence without one.
- A translated epigraph names the translator in the source line when the translation is someone
  else's.
- Italics, type size, and alignment are the designer's choice, not a rule. Chicago's own books set
  epigraphs in roman with the source flush right.

### Chapter epigraphs, for comparison (1.49)

A chapter's epigraph follows the chapter title and precedes the chapter's text, in the same form
and with the same source line. More than one is allowed. The SCFH layout decisions of 2026-10-12
(the epigraph hangs with the title, flush left; the source flush right within the epigraph's own
box) apply to these; they are recorded in the SCFH project's `CLAUDE.md`.

### Permissions (4.84)

Chicago warns that quoting a copyrighted work decoratively, as an epigraph, is a weaker fair-use
case than quoting it in argument, and that publishers often require permission, especially for
poetry and song lyrics. A one-sentence epigram from a published list, such as Perlis's, is the
slight end of the risk.


## What it means for Guffin's book layout

- Guffin's `book` export has no half title, and `[[draft-2]]` has neither a dedication nor a
  copyright page before the contents, so in the PDF the sequence collapses to **title page,
  epigraph, contents**: the epigraph on the first page after the title page, unnumbered and without
  a running head, and the contents beginning on the page after it.
- In an EPUB there are no rectos and versos, so the rule reduces to **spine order**: the epigraph's
  document comes directly after the title page and before any other document, typed as front
  matter, and it is left out of the navigation, as the contents would leave it out.
- The epigraph's own form, the source line led by an em dash, no quotation marks, no note, is
  already how the SCFH `[[Epigrams]]` page authors epigraphs and how Guffin renders them.
- Authored front-matter sections that Chicago places *before* the epigraph (a copyright page, a
  dedication) are today set after the contents, as divisions of the document. Reordering them is a
  separate design; see Q6 of [book-epigraph-design.md](book-epigraph-design.md).
