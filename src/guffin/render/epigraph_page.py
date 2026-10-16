"""The book epigraph: lifting a leading epigraph out of the document for the front matter.

Chicago (17th ed., 1.4 and 1.36) sets a book's epigraph in the front matter, after the copyright
page and the dedication and before the contents (see ``docs/chicago-front-matter.md``).  An
epigraph authored above the export root's first heading is the document's first block, which a
``book`` layout would otherwise set on the first page after the contents.
:func:`lift_leading_epigraphs` takes the run of epigraph blocks at the head of a built document so
a renderer can set them where they belong (``docs/book-epigraph-design.md``):

- the PDF renderer passes them to the template as the :data:`BOOK_EPIGRAPH_META_KEY` metadata
  value, which the template's ``epigraph.typ`` partial sets on a page of its own ahead of the
  outline;
- the EPUB renderer puts them back at the head of the document inside a
  :data:`BOOK_EPIGRAPH_CLASS` ``Div``, so Pandoc splits them into a content document of their own,
  which :func:`~guffin.render.epub_post_processing.set_epigraph_document` then finishes.

Whether a renderer lifts at all follows :attr:`~guffin.render.project.StructuralPolicy.epigraph_page`.

Public symbols:

- **Constants**: :data:`BOOK_EPIGRAPH_CLASS` — the class of the ``Div`` holding the lifted
  epigraphs in the EPUB document; :data:`BOOK_EPIGRAPH_META_KEY` — the metadata key carrying them
  to the PDF template.
- **Functions**: :func:`lift_leading_epigraphs` — remove and return a document's leading epigraphs.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so its symbols are typed as Unknown by pyright; the
# suppressed rules fire only on that propagation.

import logging
from typing import Final

import panflute as pf  # type: ignore[import-untyped]

from guffin.render.pandoc_rendering import EPIGRAPH_CLASS

logger: Final[logging.Logger] = logging.getLogger(__name__)

BOOK_EPIGRAPH_CLASS: Final[str] = "book-epigraph"
"""The class of the ``Div`` that holds the book's epigraphs at the head of the EPUB document.

The EPUB post-processing pass finds the epigraph's content document by it.
"""

BOOK_EPIGRAPH_META_KEY: Final[str] = "book-epigraph"
"""The metadata key under which the PDF renderer passes the book's epigraphs to the template.

The template reads it as the ``book-epigraph`` variable; Pandoc renders the blocks to Typst, through
the same Lua filters as the body, so the value arrives as the ``#epigraph`` helper calls the body
would have carried.
"""


def _is_epigraph_div(block: pf.Block) -> bool:
    """Whether *block* is the ``Div`` an epigraph renders to."""
    return isinstance(block, pf.Div) and EPIGRAPH_CLASS in block.classes


def lift_leading_epigraphs(doc: pf.Doc) -> list[pf.Block]:
    """Remove and return the run of epigraph blocks at the head of *doc*.

    The run is every epigraph ``Div`` (:data:`~guffin.render.pandoc_rendering.EPIGRAPH_CLASS`) from
    the start of *doc*'s content up to its first block of any other kind, which ends it: a heading,
    a paragraph, or the title Header a format renders when it has no title page.  A block reference
    to an epigraph has already been rendered as the epigraph itself by the time the document is
    built, so it is lifted like one.  Only the head of the document qualifies: an epigraph under a
    heading belongs to that division and stays.

    Args:
        doc: The built document, its vertex links resolved.  Modified in place when anything is
            lifted.

    Returns:
        The lifted blocks, in order, detached from *doc*; empty, with *doc* untouched, when its
        first block is not an epigraph.
    """
    content: Final[list[pf.Block]] = list(doc.content)
    lifted: Final[list[pf.Block]] = []
    while content and _is_epigraph_div(content[0]):
        lifted.append(content.pop(0))
    if lifted:
        doc.content = content
        logger.info("lifted %d leading epigraph(s) out of the document for the front matter", len(lifted))
    return lifted
