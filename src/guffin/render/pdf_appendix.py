"""The generated back-matter appendix that holds appendix-placed PDFs, and the anchors linking to it.

A :attr:`~guffin.model.publishing_semantics.PdfRender.APPENDIX_NATIVE` or
:attr:`~guffin.model.publishing_semantics.PdfRender.APPENDIX_IMAGE` occurrence leaves a link where
the PDF was embedded and reproduces its pages at the back of the document.  The *structure* of that
arrangement is the same in every format — one section, one labelled subsection per PDF, an internal
link from each occurrence — while only the reproduction of the pages differs (native page placement
in a PDF, rasterised images in an EPUB), so the structure lives here and the pages arrive through a
caller-supplied callback.

The section is renderer-generated rather than authored, so it carries no ``element-type`` tag; it
is stamped directly with what such a tag would have earned it — the ``unnumbered`` class, since
back matter stands outside the body's numbering.  Unnumbered headings still appear in a generated
table of contents, so the appendix and its entries stay navigable.  It is emitted at heading
level 1, which makes it a sibling of a parts book's parts rather than a section the last part
adopts.

Public symbols:

- :class:`AppendixEntries` — the PDFs an appendix must reproduce, in first-reference order.
- :func:`appendix_anchor` — the link that stands where an appendix-placed PDF was embedded.
- :func:`appendix_section` — the appendix's blocks, given a way to reproduce one PDF's pages.
- :data:`APPENDIX_EPUB_TYPE` — the EPUB structural-semantics term the section carries.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]

from guffin.model.chicago_structure import Matter
from guffin.render.epub_semantics import MATTER_DATA_ATTRIBUTE, EpubType, epub_division_for_matter

APPENDIX_ID: Final[str] = "pdf-appendix"
"""Identifier of the generated appendix section, and the stem of each subsection's identifier."""

APPENDIX_TITLE: Final[str] = "Appendix"
"""Heading text of the generated appendix section."""

APPENDIX_EPUB_TYPE: Final[EpubType] = EpubType.APPENDIX
"""The EPUB structural-semantics term the generated appendix carries.

Stamped directly rather than derived from an ``element-type`` tag: the section is
renderer-generated, so no tag exists to read it from.
"""

type AppendixEntries = dict[Path, tuple[str, list[pf.Inline]]]
"""Each PDF's subsection identifier and display label, keyed by its local path.

Insertion-ordered, so the appendix presents its entries in the order the document first referenced
them; keyed by path, so several occurrences of one PDF share a single entry and all link to it.
"""


def entry_identifier(entries: AppendixEntries, path: Path, label: list[pf.Inline]) -> str:
    """Return the appendix identifier for *path*, registering it in *entries* on first reference.

    Args:
        entries: The registry of appendix entries, mutated when *path* is new to it.
        path: The PDF's local path, which identifies the entry.
        label: The PDF's display label, used as its subsection heading.

    Returns:
        The identifier of *path*'s appendix subsection.
    """
    if path not in entries:
        entries[path] = (f"{APPENDIX_ID}-{len(entries) + 1}", deepcopy(label))
    return entries[path][0]


def appendix_anchor(label: list[pf.Inline], identifier: str, styled_label: list[pf.Inline] | None = None) -> pf.Para:
    """Return the paragraph that stands where an appendix-placed PDF was embedded.

    An ordinary internal link, which every reader supports — unlike the embedded-file actions a
    PDF attachment would need (see ``docs/pdf-render.md``).

    Args:
        label: The PDF's display label, used as the link text when *styled_label* is absent.
        identifier: The appendix subsection to link to.
        styled_label: A format-specific styling of *label*, for formats where an unstyled internal
            link is indistinguishable from the text around it.

    Returns:
        A :class:`~panflute.Para` holding the link.
    """
    return pf.Para(pf.Link(*(styled_label if styled_label is not None else label), url=f"#{identifier}"))


def appendix_section(entries: AppendixEntries, pages_blocks: Callable[[Path], list[pf.Block]]) -> list[pf.Block]:
    """Return the appendix's blocks: a section holding one labelled subsection per PDF.

    Args:
        entries: The PDFs to reproduce, in first-reference order.
        pages_blocks: Reproduces one PDF's pages as blocks, in the calling format's own terms.

    Returns:
        The appendix section's blocks, to append to the document.
    """
    blocks: Final[list[pf.Block]] = [
        pf.Header(
            pf.Str(APPENDIX_TITLE),
            level=1,
            identifier=APPENDIX_ID,
            classes=["unnumbered"],
            attributes={
                "epub:type": APPENDIX_EPUB_TYPE.value,
                MATTER_DATA_ATTRIBUTE: epub_division_for_matter(Matter.BACK).value,
            },
        )
    ]
    for path, (identifier, label) in entries.items():
        blocks.append(pf.Header(*label, level=2, identifier=identifier, classes=["unnumbered"]))
        blocks.extend(pages_blocks(path))
    return blocks
