"""Rendering of floats: numbering a built document's figures, tables, and listings, and labelling them.

A float (:mod:`~guffin.model.floats`) renders as a captioned Pandoc element carrying the float's
identifier (:func:`~guffin.render.pandoc_rendering.float_identifier`): a :class:`~panflute.Figure`
for a figure or a listing, a :class:`~panflute.Table` with its own caption for a table.  Its number
is not part of that build: it comes from the model's reading-order numbering
(:func:`~guffin.model.floats.float_numbers`), decided by the work's
:class:`~guffin.render.project.FloatNumberingStyle` and chapter level, and is written into the
caption afterwards as a label (*Figure 2.3.*), the same text in every format.  The same numbering
feeds the references the running text makes to the floats, and the lists of figures and tables a
work's front matter can hold: each is generated into an authored heading tagged
``element-type:: list-of-illustrations`` or ``list-of-tables``, never invented, and an authored
heading with nothing to list is dropped with a warning.  Code listings get no list.

Public symbols:

- **Models**: :class:`PreparedFloats` — what a document's floats resolve to: the floats by
  wrapper and their numbers.
- **Constants**: :data:`FLOAT_LIST_CLASS` — the class of the block holding a generated list.
- **Functions**: :func:`float_chapter_level` — the heading level a policy numbers floats by, if
  any; :func:`label_floats` — write each numbered float's label into its caption;
  :func:`prepare_floats` — number a document's floats and label them, returning what the link
  resolver needs; :func:`insert_float_lists` — generate the lists of figures and tables into
  their authored headings.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so its symbols are typed as Unknown by pyright; the
# document edits below are plain panflute attribute writes.

import logging
from collections.abc import Mapping
from typing import Final, NamedTuple

import panflute as pf  # type: ignore[import-untyped]
from pydantic import ConfigDict, validate_call

from guffin.model.chicago_structure import StructuralElement
from guffin.model.floats import Float, FloatNumber, float_numbers, floats_in
from guffin.model.primitives import Uid
from guffin.model.publishing_semantics import FloatKind, element_type_of_vertex
from guffin.model.vertex import HeadingVertex
from guffin.model.vertex_tree import VertexTree, transcluded_vertices
from guffin.render.pandoc_ast import detached_copy, strip_links
from guffin.render.pandoc_rendering import FLOAT_ID_PREFIX, float_identifier, heading_anchor
from guffin.render.project import FloatNumberingStyle, StructuralPolicy
from guffin.render.render_options import OutputFormat

logger: Final[logging.Logger] = logging.getLogger(__name__)

FLOAT_LIST_CLASS: Final[str] = "float-list"
"""The class of the block holding a generated list of figures or tables (EPUB)."""

_LISTED_KIND_BY_ELEMENT: Final[dict[StructuralElement, FloatKind]] = {
    StructuralElement.LIST_OF_ILLUSTRATIONS: FloatKind.FIGURE,
    StructuralElement.LIST_OF_TABLES: FloatKind.TABLE,
}


class PreparedFloats(NamedTuple):
    """A document's floats and their numbers.

    Attributes:
        floats: Every float in the tree, keyed by wrapper UID.
        numbers: Each displayed float's number, keyed by wrapper UID.
    """

    floats: Mapping[Uid, Float]
    numbers: Mapping[Uid, FloatNumber]


@validate_call
def float_chapter_level(policy: StructuralPolicy) -> int | None:
    """Return the heading level *policy* numbers floats by, or ``None`` to number straight through.

    A policy numbering by chapter numbers by its division's chapter heading level; one whose
    division has no chapters (a top-level division of sections) numbers straight through, as a
    sequential policy does.

    Args:
        policy: The work's structural policy.

    Returns:
        The chapter heading level, or ``None``.
    """
    if policy.float_numbering is not FloatNumberingStyle.BY_CHAPTER:
        return None
    return policy.top_level_division.chapter_heading_level


def _label_inlines(number: FloatNumber) -> list[pf.Inline]:
    """Return the label that leads a numbered float's caption: its kind's label and its number, in bold."""
    return [pf.Strong(pf.Str(f"{number.kind.label} {number.text}.")), pf.Space()]


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def label_floats(doc: pf.Doc, numbers: Mapping[Uid, FloatNumber]) -> None:
    """Write each numbered float's label into its caption in *doc*, in place.

    Every :class:`~panflute.Figure` or :class:`~panflute.Table` whose identifier is a float
    identifier, and whose wrapper is among *numbers*, has its caption's first block led by the
    label (*Figure 2.3.*, in bold, then a space).  A float with no number — one never displayed
    by the reading-order walk, which validation reports — keeps its bare caption.

    Args:
        doc: The document to label.
        numbers: Each displayed float's number, keyed by wrapper UID.
    """

    def _label(elem: pf.Element, _doc: pf.Doc) -> None:
        if not isinstance(elem, (pf.Figure, pf.Table)) or not elem.identifier.startswith(FLOAT_ID_PREFIX):
            return
        number: FloatNumber | None = numbers.get(elem.identifier[len(FLOAT_ID_PREFIX) :])
        if number is None:
            return
        caption_blocks: Final[list[pf.Block]] = list(elem.caption.content)
        if caption_blocks and isinstance(caption_blocks[0], (pf.Plain, pf.Para)):
            caption_blocks[0].content = pf.ListContainer(*_label_inlines(number), *caption_blocks[0].content)

    doc.walk(_label)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def prepare_floats(doc: pf.Doc, vertex_tree: VertexTree, policy: StructuralPolicy) -> PreparedFloats:
    """Number *vertex_tree*'s floats per *policy* and label them in *doc*.

    Args:
        doc: The document built from *vertex_tree*, labelled in place.
        vertex_tree: The tree whose floats to number.
        policy: The work's structural policy, giving the numbering style and the chapter level.

    Returns:
        The floats and their numbers, for the link resolver.
    """
    numbering = float_numbers(vertex_tree, float_chapter_level(policy))
    label_floats(doc, numbering.numbers)
    return PreparedFloats(floats=floats_in(vertex_tree), numbers=numbering.numbers)


def _list_heading(vertex_tree: VertexTree, element: StructuralElement) -> HeadingVertex | None:
    """Return the first render-visible heading tagged *element*, or ``None``."""
    for vertex in transcluded_vertices(vertex_tree):
        if isinstance(vertex, HeadingVertex) and element_type_of_vertex(vertex) is element:
            return vertex
    return None


def _identified_elements(doc: pf.Doc) -> dict[str, pf.Element]:
    """Return *doc*'s identified Headers, Figures, and Tables, keyed by identifier (first wins)."""
    found: Final[dict[str, pf.Element]] = {}

    def _collect(elem: pf.Element, _doc: pf.Doc) -> None:
        if isinstance(elem, (pf.Header, pf.Figure, pf.Table)) and elem.identifier:
            found.setdefault(elem.identifier, elem)

    doc.walk(_collect)
    return found


def _position(header: pf.Header) -> int:
    """Return *header*'s current position among its siblings, found by identity.

    Panflute caches an element's index when it is placed, and inserting or removing a sibling
    ahead of it leaves the cache stale, so the position is looked up afresh.
    """
    return next(index for index, block in enumerate(header.parent.content) if block is header)


def _section_end(header: pf.Header, start: int) -> int:
    """Return the index, among *header*'s siblings, of the next Header at its level or above.

    *start* is *header*'s own position.
    """
    siblings: Final[pf.ListContainer] = header.parent.content
    end: int = start + 1
    while end < len(siblings) and not (isinstance(siblings[end], pf.Header) and siblings[end].level <= header.level):
        end += 1
    return end


def _caption_inlines(element: pf.Element) -> list[pf.Inline]:
    """Return a link-free copy of the labelled caption a float's Figure or Table carries."""
    if not isinstance(element, (pf.Figure, pf.Table)):
        return []
    blocks: Final[list[pf.Block]] = list(element.caption.content)
    if not blocks or not isinstance(blocks[0], (pf.Plain, pf.Para)):
        return []
    return strip_links(detached_copy(list(blocks[0].content)))


def _typst_outline(wrapper_uids: list[Uid]) -> pf.RawBlock:
    """Return a raw Typst outline of exactly the floats *wrapper_uids*, by their labels, with page numbers."""
    labels: Final[list[str]] = [f"<{float_identifier(uid)}>" for uid in wrapper_uids]
    selector: Final[str] = f"selector({labels[0]})" + (f".or({', '.join(labels[1:])})" if len(labels) > 1 else "")
    # Panflute's RawBlock constructor predates Pandoc's Typst support, so the format is set after.
    raw: Final[pf.RawBlock] = pf.RawBlock(f"#outline(title: none, target: {selector})", format="html")
    raw.format = "typst"
    return raw


def _linked_list(wrapper_uids: list[Uid], elements: Mapping[str, pf.Element]) -> pf.BulletList:
    """Return a bullet list of links, each a float's labelled caption pointing at the float."""
    return pf.BulletList(
        *(
            pf.ListItem(
                pf.Plain(pf.Link(*_caption_inlines(elements[float_identifier(uid)]), url=f"#{float_identifier(uid)}"))
            )
            for uid in wrapper_uids
            if float_identifier(uid) in elements
        )
    )


def _list_blocks(
    wrapper_uids: list[Uid], elements: Mapping[str, pf.Element], output_format: OutputFormat
) -> list[pf.Block]:
    """Return the blocks of one generated list in *output_format*."""
    match output_format:
        case OutputFormat.PDF:
            return [_typst_outline(wrapper_uids)]
        case OutputFormat.EPUB:
            return [pf.Div(_linked_list(wrapper_uids, elements), classes=[FLOAT_LIST_CLASS])]
        case OutputFormat.MARKDOWN:
            return [_linked_list(wrapper_uids, elements)]


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def insert_float_lists(
    doc: pf.Doc,
    vertex_tree: VertexTree,
    numbers: Mapping[Uid, FloatNumber],
    output_format: OutputFormat,
) -> None:
    """Generate the lists of figures and tables into their authored headings in *doc*, in place.

    The first render-visible heading tagged ``element-type:: list-of-illustrations`` receives the
    list of figures, the first tagged ``list-of-tables`` the list of tables, each after the
    section's own content: in the PDF a Typst outline of exactly those floats, by their labels,
    with page numbers; in the EPUB and Markdown a bullet list of links, each the float's labelled
    caption pointing at it (the EPUB's list wrapped in a :data:`FLOAT_LIST_CLASS` block for its
    stylesheet).  Floats are listed in their numbering's order, which is reading order.  A list
    heading whose kind has no displayed float is removed with its section, and a warning logged,
    since an empty list says nothing.  Without such a heading no list is made.

    Run after the floats are labelled and the vertex links resolved, so each caption is copied
    labelled and its links can be flattened to their display text.

    Args:
        doc: The built, labelled, and resolved document.
        vertex_tree: The tree *doc* was built from, giving the list headings.
        numbers: Each displayed float's number, keyed by wrapper UID, in reading order.
        output_format: The format being rendered, which decides each list's form.
    """
    elements: Final[dict[str, pf.Element]] = _identified_elements(doc)
    for element, kind in _LISTED_KIND_BY_ELEMENT.items():
        heading: HeadingVertex | None = _list_heading(vertex_tree, element)
        if heading is None:
            continue
        header: pf.Element | None = elements.get(heading_anchor(heading.uid))
        if not isinstance(header, pf.Header):
            continue
        listed: list[Uid] = [uid for uid, number in numbers.items() if number.kind is kind]
        start: int = _position(header)
        end: int = _section_end(header, start)
        siblings: pf.ListContainer = header.parent.content
        if not listed:
            logger.warning(
                "the %s heading uid=%r has no %s floats to list; its section is left out",
                element.value,
                heading.uid,
                kind.value,
            )
            for _ in range(end - start):
                siblings.pop(start)
            continue
        for offset, block in enumerate(_list_blocks(listed, elements, output_format)):
            siblings.insert(end + offset, block)
