"""Floats — the numbered figures, tables, and listings of a document, and the references to them.

A *float* is a captioned element the running text refers to by number rather than by position:
a figure, a table, or a listing.  It is declared by a **wrapper**: a text vertex tagged with a
:class:`~guffin.model.publishing_semantics.FloatKind` (the ``float`` tag), whose text is the
caption and whose one child is the wrapped content — an image, a table, or a code block of the
kind's content type, either directly or as a standalone reference to one.  The wrapper's UID is
the float's identity: a reference to the float points at the wrapper, and the float is displayed
wherever the wrapper is, or wherever an embed or a standalone reference of the wrapper sits.

Floats are numbered where they are **displayed**, in reading order, in one series per kind, and
in a document with chapters the number restarts at each body-matter chapter and is prefixed by
the chapter's number (*figure 2.3*).  The first display of a float numbers it; a later display
is a repeat.

A reference's display text that is exactly a kind's word (*figure*, *table*, *listing*, in any
case) is a **kind word**: a reference asking to be completed with the float's number.

Public symbols:

- **Models**: :class:`Float` — a float: its wrapper, kind, caption, and content;
  :class:`PlacedFloat` — a float at a display site, with the headings governing its position;
  :class:`FloatNumber` — a float's number, with its chapter when numbered by chapter;
  :class:`FloatNumbering` — every displayed float's number, and the repeated displays;
  :class:`FloatReference` — one inline reference to a float, with its display text and whether
  that text is a kind word.
- **Functions**: :func:`kind_word` — the :class:`~guffin.model.publishing_semantics.FloatKind` a
  display text names, if it is a kind word; :func:`float_of_wrapper` — the float a vertex
  declares, if it is a well-formed wrapper; :func:`float_content` — the vertex a wrapper's child
  displays; :func:`floats_in` — every well-formed float in a tree, keyed by wrapper;
  :func:`placed_floats` — every display of a float in reading order, with its governing
  headings; :func:`float_numbers` — the numbering of a tree's displayed floats;
  :func:`float_references` — every inline reference to a wrapper in the render-visible document;
  :func:`kind_word_references` — every inline reference whose display text is a kind word,
  whatever it points at.
"""

from collections.abc import Mapping
from typing import Final, NamedTuple

from pydantic import validate_call

from guffin.model.chicago_structure import Matter
from guffin.model.notes import vertex_texts
from guffin.model.primitives import Uid
from guffin.model.publishing_semantics import FloatKind, float_of_vertex, resolved_matter
from guffin.model.vertex import HeadingVertex, NotesVertex, TextVertex, Vertex, is_embed_vertex
from guffin.model.vertex_link import VertexLinkKind, parse_standalone_vertex_link, vertex_links_in_text
from guffin.model.vertex_tree import VertexTree, root_vertex, standalone_link_target, transcluded_vertices


class Float(NamedTuple):
    """A float: a wrapper's kind, caption, and content.

    Attributes:
        wrapper_uid: The UID of the wrapper, the float's identity.
        kind: The float's kind.
        caption: The caption, the wrapper's text.
        content_uid: The UID of the wrapped content vertex, the one the wrapper's child displays.
    """

    wrapper_uid: Uid
    kind: FloatKind
    caption: str
    content_uid: Uid


class PlacedFloat(NamedTuple):
    """A float at one display site, with the headings governing that site.

    Attributes:
        float: The float displayed.
        headings: The headings governing the site, one per level, outermost first.
    """

    float: Float
    headings: tuple[HeadingVertex, ...]


class FloatNumber(NamedTuple):
    """A float's number.

    Attributes:
        kind: The float's kind, whose series the number counts in.
        chapter: The number of the chapter the float is in, when numbered by chapter; ``None``
            when numbered straight through, or when the float sits outside every chapter.
        ordinal: The float's position in its series, from 1, restarting with each chapter when
            numbered by chapter.
    """

    kind: FloatKind
    chapter: int | None
    ordinal: int

    @property
    def text(self) -> str:
        """The number as set: ``2.3`` by chapter, ``3`` straight through."""
        return f"{self.chapter}.{self.ordinal}" if self.chapter is not None else str(self.ordinal)


class FloatNumbering(NamedTuple):
    """The numbering of a tree's displayed floats.

    Attributes:
        numbers: Each displayed float's number, keyed by wrapper UID, from its first display.
        repeated: The wrapper UIDs displayed more than once, in order of their second display.
    """

    numbers: dict[Uid, FloatNumber]
    repeated: tuple[Uid, ...]


class FloatReference(NamedTuple):
    """One inline reference to a float wrapper in the running text.

    Attributes:
        citing_uid: The UID of the vertex whose text carries the reference.
        display: The reference's display text, the alias the author wrote.
        wrapper_uid: The UID of the wrapper referenced.
        kind_word: The kind the display text names, when it is a kind word; else ``None``.
    """

    citing_uid: Uid
    display: str
    wrapper_uid: Uid
    kind_word: FloatKind | None


_KIND_BY_WORD: Final[dict[str, FloatKind]] = {kind.value: kind for kind in FloatKind}


@validate_call
def kind_word(display: str) -> FloatKind | None:
    """Return the :class:`~guffin.model.publishing_semantics.FloatKind` *display* names, if it is a kind word.

    A kind word is a display text that is exactly a kind's word, compared without regard to case
    or surrounding whitespace: ``figure``, ``Figure``, ``TABLE``.  Anything else — a plural, an
    abbreviation, a phrase holding the word — is not.

    Args:
        display: A reference's display text.

    Returns:
        The kind named, or ``None``.
    """
    return _KIND_BY_WORD.get(display.strip().lower())


@validate_call
def float_content(wrapper: Vertex, tree: VertexTree) -> Vertex | None:
    """Return the vertex a wrapper's child displays, or ``None`` when the wrapper has no single child.

    The child displays itself, or, when it is a standalone reference to a vertex in *tree*, that
    vertex (:func:`~guffin.model.vertex_tree.standalone_link_target`).  The wrapped content's kind
    is not checked here.

    Args:
        wrapper: The candidate wrapper vertex.
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` providing the UID-to-vertex lookup.

    Returns:
        The displayed vertex, or ``None`` when *wrapper* has no child, more than one, or a child
        absent from the tree.
    """
    children: Final[tuple[Uid, ...]] = tuple(wrapper.children or ())
    if len(children) != 1 or children[0] not in tree.uid_map:
        return None
    child: Final[Vertex] = tree.uid_map[children[0]]
    target: Final[Vertex | None] = standalone_link_target(child, tree)
    return child if target is None else target


@validate_call
def float_of_wrapper(vertex: Vertex, tree: VertexTree) -> Float | None:
    """Return the float *vertex* declares, or ``None`` when it is not a well-formed wrapper.

    A well-formed wrapper is a :class:`~guffin.model.vertex.TextVertex` carrying a ``float`` tag
    whose one child displays (:func:`float_content`) a vertex of the kind's content type.  A
    tagged vertex that is not well formed is not a float; validation reports it.

    Args:
        vertex: The candidate wrapper.
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` providing the UID-to-vertex lookup.

    Returns:
        The :class:`Float`, or ``None``.
    """
    if not isinstance(vertex, TextVertex):
        return None
    kind: Final[FloatKind | None] = float_of_vertex(vertex)
    if kind is None:
        return None
    content: Final[Vertex | None] = float_content(vertex, tree)
    if content is None or content.vertex_type is not kind.content_type:
        return None
    return Float(wrapper_uid=vertex.uid, kind=kind, caption=vertex.text, content_uid=content.uid)


@validate_call
def floats_in(tree: VertexTree) -> dict[Uid, Float]:
    """Return every well-formed float in *tree*, keyed by wrapper UID.

    Every vertex of the tree is a candidate, the referenced vertices included, since a float kept
    on another page is still a float, whether or not this document displays it (which
    :func:`placed_floats` tells).

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.

    Returns:
        The floats, keyed by wrapper UID, in the tree's vertex order.
    """
    floats: Final[dict[Uid, Float]] = {}
    for vertex in tree.uid_map.values():
        found: Float | None = float_of_wrapper(vertex, tree)
        if found is not None:
            floats[found.wrapper_uid] = found
    return floats


@validate_call
def placed_floats(tree: VertexTree) -> list[PlacedFloat]:
    """Return every display of a float in *tree*'s rendered document, in reading order, with its governing headings.

    Walks the rendered document pre-order from the root, as a reader meets it: each vertex's
    children in order, an embed's target subtree descending at the embed site, and a standalone
    reference to a wrapper descending into the wrapper, since such a reference displays the
    float.  A heading governs everything after it in reading order until the next heading at its
    level or above.  The notes containers are not part of the running text, so the walk does not
    enter them.  A wrapper reached twice is listed twice, once per display; every other vertex is
    visited once (cycles terminate).

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to walk.

    Returns:
        One :class:`PlacedFloat` per display, in reading order.
    """
    placed: Final[list[PlacedFloat]] = []
    governing: dict[int, HeadingVertex] = {}
    seen: Final[set[Uid]] = set()
    stack: Final[list[Vertex]] = [root_vertex(tree)]
    while stack:
        vertex: Vertex = stack.pop()
        if isinstance(vertex, NotesVertex):
            continue
        found: Float | None = float_of_wrapper(vertex, tree)
        if found is None and vertex.uid in seen:
            continue
        seen.add(vertex.uid)
        if isinstance(vertex, HeadingVertex):
            governing = {level: heading for level, heading in governing.items() if level < vertex.heading_level}
            governing[vertex.heading_level] = vertex
        if found is not None:
            placed.append(PlacedFloat(float=found, headings=tuple(governing[level] for level in sorted(governing))))
            continue
        frames: list[Vertex] = [tree.uid_map[uid] for uid in vertex.children or () if uid in tree.uid_map]
        if is_embed_vertex(vertex) and vertex.vertex_link.uid in tree.uid_map:
            frames.insert(0, tree.uid_map[vertex.vertex_link.uid])
        displayed: Vertex | None = standalone_link_target(vertex, tree)
        if displayed is not None and float_of_wrapper(displayed, tree) is not None:
            frames.insert(0, displayed)
        stack.extend(reversed(frames))
    return placed


def _is_chapter(heading: HeadingVertex) -> bool:
    """Return whether *heading* is a body-matter heading: one that counts as a chapter."""
    return resolved_matter(heading) in (None, Matter.BODY)


@validate_call
def float_numbers(tree: VertexTree, chapter_level: int | None) -> FloatNumbering:
    """Return the numbering of *tree*'s displayed floats.

    Each kind is numbered in its own series in reading order (:func:`placed_floats`).  With a
    *chapter_level*, the series restart at each body-matter heading of that level, and each
    number carries the ordinal of that heading among the body-matter headings of the level met
    so far; a float displayed before any such heading, or under a front- or back-matter one,
    carries no chapter and counts in a series of its own.  Without a *chapter_level* every series
    runs straight through.  A float's number is assigned at its first display; later displays
    are reported as repeats.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` whose floats to number.
        chapter_level: The heading level of a chapter, or ``None`` to number straight through.

    Returns:
        The :class:`FloatNumbering`.
    """
    numbers: Final[dict[Uid, FloatNumber]] = {}
    repeated: Final[list[Uid]] = []
    ordinals: dict[tuple[FloatKind, int | None], int] = {}
    chapter_of: Final[dict[Uid, int]] = {}
    for placed in placed_floats(tree):
        chapter: int | None = None
        if chapter_level is not None:
            heading: HeadingVertex | None = next(
                (candidate for candidate in placed.headings if candidate.heading_level == chapter_level), None
            )
            if heading is not None and _is_chapter(heading):
                chapter = chapter_of.setdefault(heading.uid, len(chapter_of) + 1)
        wrapper_uid: Uid = placed.float.wrapper_uid
        if wrapper_uid in numbers:
            repeated.append(wrapper_uid)
            continue
        series: tuple[FloatKind, int | None] = (placed.float.kind, chapter)
        ordinals[series] = ordinals.get(series, 0) + 1
        numbers[wrapper_uid] = FloatNumber(kind=placed.float.kind, chapter=chapter, ordinal=ordinals[series])
    return FloatNumbering(numbers=numbers, repeated=tuple(repeated))


def _inline_references(tree: VertexTree) -> list[tuple[Uid, str, Uid]]:
    """Return every inline, non-note vertex link in *tree*'s render-visible texts.

    Each as ``(citing uid, display, target uid)``.

    A text that is nothing but a vertex link is a standalone reference, which displays its target
    rather than referring to it, so its link is left out.
    """
    found: Final[list[tuple[Uid, str, Uid]]] = []
    for vertex in transcluded_vertices(tree):
        for text in vertex_texts(vertex):
            if parse_standalone_vertex_link(text) is not None:
                continue
            found.extend(
                (vertex.uid, display, link.uid)
                for display, link in vertex_links_in_text(text)
                if link.kind is not VertexLinkKind.NOTE
            )
    return found


@validate_call
def kind_word_references(tree: VertexTree) -> list[FloatReference]:
    """Return every inline reference in *tree*'s render-visible document whose display text is a kind word.

    Whatever the reference points at: a wrapper of the named kind, a wrapper of another, or a
    vertex that is no wrapper at all.  Each reference's ``kind_word`` is the kind its display
    names, never ``None``.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.

    Returns:
        The references, in render-visible order.
    """
    return [
        FloatReference(citing_uid=citing_uid, display=display, wrapper_uid=target_uid, kind_word=kind)
        for citing_uid, display, target_uid in _inline_references(tree)
        if (kind := kind_word(display)) is not None
    ]


@validate_call
def float_references(tree: VertexTree, floats: Mapping[Uid, Float]) -> list[FloatReference]:
    """Return every inline reference to a float wrapper in *tree*'s render-visible document.

    An inline reference is a vertex link amid a text (a text that is itself nothing but the
    link is a standalone reference, which displays the float and is not listed), of
    :attr:`~guffin.model.vertex_link.VertexLinkKind.REFERENCE` or
    :attr:`~guffin.model.vertex_link.VertexLinkKind.EMBED` kind, whose destination is one of
    *floats*' wrappers.  Each carries its display text and whether that text is a kind word.

    Args:
        tree: The :class:`~guffin.model.vertex_tree.VertexTree` to search.
        floats: The floats to look for, keyed by wrapper UID (see :func:`floats_in`).

    Returns:
        The references, in render-visible order.
    """
    return [
        FloatReference(citing_uid=citing_uid, display=display, wrapper_uid=target_uid, kind_word=kind_word(display))
        for citing_uid, display, target_uid in _inline_references(tree)
        if target_uid in floats
    ]
