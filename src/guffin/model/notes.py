"""Notes — note links in the running text, the notes they point at, and the containers holding them.

A note annotates a passage of the running text.  The passage carries a
:attr:`~guffin.model.vertex_link.VertexLinkKind.NOTE` link whose display text is the note's
*lead-in* (a phrase of the passage, which stays in the running text) and whose destination is
the note: an ordinary vertex, one child of a :class:`~guffin.model.vertex.NotesVertex`.

Public symbols:

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
  :func:`orphan_note_uids` — the notes no note link cites; :func:`is_numbered_lead_in` —
  whether a lead-in is only a number (an unrenamed numbered marker's label);
  :func:`strip_note_links` — reduce every note link in a tree to plain text, for notes left out.
"""

from collections.abc import Sequence
from typing import Final, NamedTuple

import regex
from pydantic import validate_call

from guffin.model.primitives import Uid
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
from guffin.model.vertex_link import VertexLinkKind, vertex_link_spans, vertex_links_in_text
from guffin.model.vertex_tree import VertexTree, map_vertices, root_vertex, transcluded_vertices


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


_NUMBERED_LEAD_IN_RE: Final[regex.Pattern[str]] = regex.compile(r"\d+")
"""A lead-in that is only digits: a note number, not a phrase of the passage."""


@validate_call
def is_numbered_lead_in(lead_in: str) -> bool:
    """Whether *lead_in* is only a number, ignoring surrounding whitespace.

    The Footnotes extension labels a new note with its number (``[(1)](((uid)))``), and until the
    author renames it the label is the note's number rather than a phrase of the passage.

    Args:
        lead_in: A note link's display text.

    Returns:
        ``True`` when *lead_in* is one or more digits and nothing else.
    """
    return _NUMBERED_LEAD_IN_RE.fullmatch(lead_in.strip()) is not None


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


def _without_note_links(text: str) -> str:
    """Return *text* with each note link reduced to its lead-in, and a numbered one removed.

    A numbered lead-in (see :func:`is_numbered_lead_in`) or an empty one takes the spaces before it
    along, unless a letter or digit follows the link directly, so no gap is left before the next
    word or the punctuation.
    """
    pieces: Final[list[str]] = []
    position: int = 0
    for start, end, display, link in vertex_link_spans(text):
        if link.kind is not VertexLinkKind.NOTE:
            continue
        before: str = text[position:start]
        if not display.strip() or is_numbered_lead_in(display):
            if not text[end : end + 1].isalnum():
                before = before.rstrip(" \t")
            pieces.append(before)
        else:
            pieces.extend((before, display))
        position = end
    pieces.append(text[position:])
    return "".join(pieces)


def _inline_texts(vertex: Vertex) -> tuple[str, ...]:
    """Return every inline text *vertex* carries: :func:`vertex_texts` plus any alternative wordings."""
    alternatives: Final[tuple[str, ...]] = (
        tuple(alternative.text for alternative in vertex.alternatives or ()) if isinstance(vertex, TextVertex) else ()
    )
    return (*vertex_texts(vertex), *alternatives)


def _with_note_links_stripped(vertex: Vertex) -> Vertex:
    """Return *vertex* with the note links in each of its inline texts reduced (see :func:`_without_note_links`)."""
    match vertex:
        case TextVertex():
            return vertex.model_copy(
                update={
                    "text": _without_note_links(vertex.text),
                    "alternatives": (
                        None
                        if vertex.alternatives is None
                        else tuple(
                            alternative.model_copy(update={"text": _without_note_links(alternative.text)})
                            for alternative in vertex.alternatives
                        )
                    ),
                }
            )
        case HeadingVertex() | TodoVertex():
            return vertex.model_copy(update={"text": _without_note_links(vertex.text)})
        case PageVertex():
            return vertex.model_copy(update={"title": _without_note_links(vertex.title)})
        case CalloutVertex():
            return vertex.model_copy(
                update={"title": _without_note_links(vertex.title), "body": _without_note_links(vertex.body)}
            )
        case QuoteBlockVertex():
            return vertex.model_copy(
                update={
                    "quote": _without_note_links(vertex.quote),
                    "attribution": None if vertex.attribution is None else _without_note_links(vertex.attribution),
                }
            )
        case TableVertex():
            rows: Final[tuple[tuple[str, ...], ...]] = tuple(
                tuple(_without_note_links(cell) for cell in row) for row in vertex.table.rows
            )
            return vertex.model_copy(update={"table": vertex.table.model_copy(update={"rows": rows})})
        case ImageVertex():
            return vertex.model_copy(
                update={"alt_text": None if vertex.alt_text is None else _without_note_links(vertex.alt_text)}
            )
        case _:
            return vertex


@validate_call
def strip_note_links(tree: VertexTree) -> VertexTree:
    """Return a new :class:`~guffin.model.vertex_tree.VertexTree` whose note links are reduced to plain text.

    For a tree whose notes are left out.  Each note link in a vertex's inline texts (those
    :func:`vertex_texts` names, and a text vertex's alternative wordings) becomes its lead-in as
    plain text, so the passage reads as if it had never cited a note.  A lead-in that is only a
    number (see :func:`is_numbered_lead_in`) names no phrase of the passage, so it is removed,
    together with the spaces before it unless a letter or digit follows directly: ``a word (1)
    here`` and ``a word(1) here`` both become ``a word here``.  Other vertex links are untouched.
    The original *tree* is not modified; it passes through unchanged when it has no note links.

    Args:
        tree: The source :class:`~guffin.model.vertex_tree.VertexTree`.

    Returns:
        A new tree without note links, or *tree* itself when it has none.
    """
    if not any(note_links_in_text(text) for vertex in tree.uid_map.values() for text in _inline_texts(vertex)):
        return tree
    return map_vertices(tree, _with_note_links_stripped)
