"""Notes — note links in the running text, the notes they point at, and the containers holding them.

A note annotates a passage of the running text.  The passage carries a
:attr:`~guffin.model.vertex_link.VertexLinkKind.NOTE` link whose display text is the note's
*lead-in* (a phrase of the passage, which stays in the running text) and whose destination is
the note: an ordinary vertex, one child of a :class:`~guffin.model.vertex.NotesVertex`.

Public symbols:

- **Constants**: :data:`NOTES_SECTION_TITLE` — the title of a Notes section Guffin adds;
  :data:`ADDED_NOTES_HEADING_UID` — the UID of the heading it adds.
- **Models**: :class:`NoteCitation` — one note link in the render-visible document: the vertex
  whose text carries it, its lead-in, and the note's UID; :class:`PlacedNoteCitation` — a note
  link with the headings governing its position, and its
  :meth:`~PlacedNoteCitation.group_heading` at a given level.
- **Functions**: :func:`note_links_in_text` — every note link in a text, as ``(lead-in, uid)``
  pairs in text order; :func:`vertex_texts` — the inline texts a vertex renders;
  :func:`note_citations` — every note link in a tree's render-visible document;
  :func:`placed_note_citations` — every note link in reading order, with its governing headings;
  :func:`notes_containers` — every :class:`~guffin.model.vertex.NotesVertex` in a tree;
  :func:`contained_note_uids` — the UIDs of every note held by a notes container;
  :func:`orphan_note_uids` — the notes no note link cites; :func:`with_notes_section` — a tree that
  cites notes but has no Notes heading, with one added at the end of its root.
"""

from collections.abc import Sequence
from typing import Final, NamedTuple

from pydantic import validate_call

from guffin.model.attribute import AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.chicago_structure import StructuralElement
from guffin.model.primitives import Uid
from guffin.model.publishing_semantics import PublishingSemantics, has_element_type
from guffin.model.vertex import (
    CalloutVertex,
    HeadingVertex,
    ImageVertex,
    NotesVertex,
    PageVertex,
    QuoteBlockVertex,
    TableVertex,
    TextVertex,
    TodoVertex,
    Vertex,
    is_embed_vertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_links_in_text
from guffin.model.vertex_tree import VertexTree, root_vertex, transcluded_vertices

NOTES_SECTION_TITLE: Final[str] = "Notes"
"""The title of a Notes section Guffin adds (see :func:`with_notes_section`), Chicago's own term."""

ADDED_NOTES_HEADING_UID: Final[Uid] = "guffinNts"
"""The UID of the Notes heading :func:`with_notes_section` adds.

The heading comes from no source graph, so its UID is a fixed, recognisable value rather than one a
source assigned.
"""

_ADDED_ATTRIBUTE_PAGE_UID: Final[Uid] = "guffinAtt"
"""The UID the added heading's ``element-type`` assignment links to as its attribute page.

An :class:`~guffin.model.attribute.AttributeInstance` links to its attribute's page in the graph it
was read from; an assignment Guffin adds was read from no graph, so the link names no page.
"""


class NoteCitation(NamedTuple):
    """One note link in the render-visible document.

    Attributes:
        citing_uid: The UID of the vertex whose text carries the link.
        lead_in: The link's display text, the note's lead-in.
        note_uid: The UID of the note the link points at.
    """

    citing_uid: Uid
    lead_in: str
    note_uid: Uid


class PlacedNoteCitation(NamedTuple):
    """A note link together with the headings in force where it appears in the rendered document.

    Attributes:
        citation: The note link.
        headings: The headings governing the link's position, one per level, by increasing level:
            the most recent heading of each level above the link in reading order.
    """

    citation: NoteCitation
    headings: tuple[HeadingVertex, ...]

    @validate_call
    def group_heading(self, level: int) -> HeadingVertex | None:
        """Return the deepest governing heading at *level* or above, or ``None`` when there is none.

        Args:
            level: The deepest heading level to consider.

        Returns:
            The governing heading with the largest level not exceeding *level*.
        """
        eligible: Final[list[HeadingVertex]] = [heading for heading in self.headings if heading.heading_level <= level]
        return eligible[-1] if eligible else None


@validate_call
def note_links_in_text(text: str) -> list[tuple[str, Uid]]:
    """Return every note link in *text*, as ``(lead-in, uid)`` pairs in text order.

    A note link is a :attr:`~guffin.model.vertex_link.VertexLinkKind.NOTE` vertex link (per
    :func:`~guffin.model.vertex_link.vertex_links_in_text`); its display text is the lead-in.

    Args:
        text: A Pandoc-Markdown text.

    Returns:
        One pair per note link; empty when *text* has none.
    """
    return [(display, link.uid) for display, link in vertex_links_in_text(text) if link.kind is VertexLinkKind.NOTE]


@validate_call
def vertex_texts(vertex: Vertex) -> tuple[str, ...]:
    """Return the inline texts *vertex* renders, in display order.

    Only the selected wording of a :class:`~guffin.model.vertex.TextVertex` counts, not its
    alternatives.  A code listing is literal, never inline text, so it contributes nothing.

    Args:
        vertex: The vertex whose texts to return.

    Returns:
        The vertex's inline texts; empty for a vertex type that carries none.
    """
    match vertex:
        case PageVertex():
            return (vertex.title,)
        case HeadingVertex() | TextVertex() | TodoVertex():
            return (vertex.text,)
        case CalloutVertex():
            return (vertex.title, vertex.body)
        case QuoteBlockVertex():
            return (vertex.quote,) if vertex.attribution is None else (vertex.quote, vertex.attribution)
        case TableVertex():
            return tuple(cell for row in vertex.table.rows for cell in row)
        case ImageVertex():
            return () if vertex.alt_text is None else (vertex.alt_text,)
        case _:
            return ()


@validate_call
def note_citations(tree: VertexTree) -> list[NoteCitation]:
    """Return every note link in *tree*'s render-visible document.

    The render-visible document is the tree vertices plus all content transcluded through
    embeds (per :func:`~guffin.model.vertex_tree.transcluded_vertices`); each vertex is visited
    once.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.

    Returns:
        One :class:`NoteCitation` per note link, grouped by vertex in render-visible order and in
        text order within a vertex.
    """
    return [
        NoteCitation(citing_uid=vertex.uid, lead_in=lead_in, note_uid=note_uid)
        for vertex in transcluded_vertices(tree)
        for text in vertex_texts(vertex)
        for lead_in, note_uid in note_links_in_text(text)
    ]


@validate_call
def placed_note_citations(tree: VertexTree) -> list[PlacedNoteCitation]:
    """Return every note link in *tree*'s rendered document, in reading order, with its governing headings.

    Walks the rendered document pre-order from the root: each vertex's children in order, with an
    embed's target subtree descending at the embed site, so transcluded content appears where it
    renders.  A heading governs everything after it in reading order until the next heading at its
    level or above, whether that content is nested under it or follows it.  The notes containers
    are not part of the running text, so the walk does not enter them.  Each vertex is visited
    once (cycles terminate); embed targets absent from
    :attr:`~guffin.model.vertex_tree.VertexTree.uid_map` are skipped.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to walk.

    Returns:
        One :class:`PlacedNoteCitation` per note link, in reading order.
    """
    placed: Final[list[PlacedNoteCitation]] = []
    governing: dict[int, HeadingVertex] = {}
    seen: Final[set[Uid]] = set()
    stack: Final[list[Vertex]] = [root_vertex(tree)]
    while stack:
        vertex: Vertex = stack.pop()
        if vertex.uid in seen or isinstance(vertex, NotesVertex):
            continue
        seen.add(vertex.uid)
        if isinstance(vertex, HeadingVertex):
            governing = {level: heading for level, heading in governing.items() if level < vertex.heading_level}
            governing[vertex.heading_level] = vertex
        headings: tuple[HeadingVertex, ...] = tuple(governing[level] for level in sorted(governing))
        placed.extend(
            PlacedNoteCitation(
                citation=NoteCitation(citing_uid=vertex.uid, lead_in=lead_in, note_uid=note_uid), headings=headings
            )
            for text in vertex_texts(vertex)
            for lead_in, note_uid in note_links_in_text(text)
        )
        frames: list[Vertex] = [tree.uid_map[uid] for uid in vertex.children or () if uid in tree.uid_map]
        if is_embed_vertex(vertex) and vertex.vertex_link.uid in tree.uid_map:
            frames.insert(0, tree.uid_map[vertex.vertex_link.uid])
        stack.extend(reversed(frames))
    return placed


@validate_call
def notes_containers(tree: VertexTree) -> list[NotesVertex]:
    """Return every :class:`~guffin.model.vertex.NotesVertex` in *tree*'s render-visible document.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.

    Returns:
        The notes containers, in render-visible order.
    """
    return [vertex for vertex in transcluded_vertices(tree) if isinstance(vertex, NotesVertex)]


@validate_call
def contained_note_uids(tree: VertexTree) -> frozenset[Uid]:
    """Return the UIDs of every note held by a notes container in *tree*.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.

    Returns:
        The UIDs of every child of every :class:`~guffin.model.vertex.NotesVertex` (per
        :func:`notes_containers`).
    """
    return frozenset(uid for container in notes_containers(tree) for uid in container.children or ())


@validate_call
def orphan_note_uids(tree: VertexTree, citations: Sequence[NoteCitation]) -> list[Uid]:
    """Return the notes in *tree* that no note link in *citations* points at.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` holding the notes containers.
        citations: The note links to count as citing (typically :func:`note_citations` of *tree*).

    Returns:
        The uncited notes' UIDs, in container order.
    """
    cited: Final[frozenset[Uid]] = frozenset(citation.note_uid for citation in citations)
    return [uid for container in notes_containers(tree) for uid in container.children or () if uid not in cited]


@validate_call
def with_notes_section(tree: VertexTree) -> VertexTree:
    """Return *tree* with a Notes section added at its end, when it cites notes but has none.

    When the render-visible document cites a note (per :func:`note_citations`) and no
    render-visible heading is tagged ``element-type:: endnotes``, a heading titled
    :data:`NOTES_SECTION_TITLE` and carrying that tag (the assignment a ``guffin-meta::`` child
    would make) is appended as the root's last child, so the notes have a home.  It sits at the
    shallowest heading level the document uses (level 1 when it has none) and has UID
    :data:`ADDED_NOTES_HEADING_UID`.  Otherwise *tree* is returned unchanged.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new :class:`~guffin.model.vertex_tree.VertexTree` with the Notes heading added, or *tree*
        itself when it cites no notes or already has a Notes heading.
    """
    if not note_citations(tree) or has_element_type(tree, StructuralElement.ENDNOTES):
        return tree
    levels: Final[list[int]] = [
        vertex.heading_level for vertex in transcluded_vertices(tree) if isinstance(vertex, HeadingVertex)
    ]
    tag: Final[AttributeAssignment] = AttributeAssignment(
        attribute=AttributeInstance(
            definition=PublishingSemantics.ELEMENT_TYPE.value,
            link=VertexLink(kind=VertexLinkKind.REFERENCE, uid=_ADDED_ATTRIBUTE_PAGE_UID),
        ),
        values=(LiteralValue(value=StructuralElement.ENDNOTES.value),),
    )
    heading: Final[HeadingVertex] = HeadingVertex(
        uid=ADDED_NOTES_HEADING_UID,
        text=NOTES_SECTION_TITLE,
        heading_level=min(levels, default=1),
        attribute_assignments=[tag],
    )
    root: Final[Vertex] = root_vertex(tree)
    rooted: Final[Vertex] = root.model_copy(update={"children": [*(root.children or []), heading.uid]})
    return VertexTree(
        tree_vertices=[rooted if vertex.uid == root.uid else vertex for vertex in tree.tree_vertices] + [heading],
        ref_vertices=tree.ref_vertices,
    )
