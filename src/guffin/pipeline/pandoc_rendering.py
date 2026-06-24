"""Shared Pandoc/panflute rendering utilities for :class:`~guffin.vertex_tree.VertexTree` → :class:`~panflute.Doc`.

Converts the normalized vertex tree produced by
:func:`~guffin.pipeline.roam_tree_to_vertex_tree.transcribe` into a Panflute
:class:`~panflute.Doc` (the Pandoc object model), with inline Pandoc Markdown
properly parsed into structured panflute inline elements.

The resulting :class:`~panflute.Doc` is an output-format-neutral intermediate
representation; serializing it to a concrete target format is left to the
caller.

Inline parsing:

Text fields on :class:`~guffin.vertex.HeadingVertex` and
:class:`~guffin.vertex.TextVertex` contain normalized Pandoc Markdown
(e.g. ``**bold**``, ``*italic*``, `` `code` ``, ``[text]{.mark}``).
:func:`parse_inline_md` batches all unique text strings into a single
Pandoc parse call, returning a mapping from text string to the corresponding
list of panflute inline elements.  This avoids per-block subprocess overhead
while correctly handling all Pandoc Markdown inline syntax.

Rendering rules:

- :class:`~guffin.vertex.PageVertex` — when *title_in_header* is ``True``,
  title rendered as an H1 :class:`~panflute.Header` in the document body;
  when ``False``, title stored as the Pandoc document metadata ``title``.
  Children rendered at depth 1 in both cases.
- :class:`~guffin.vertex.HeadingVertex` — rendered as a
  :class:`~panflute.Header` at the vertex's recorded heading level.
- :class:`~guffin.vertex.TextVertex` — laid out per the parent's
  :class:`~guffin.model.view.ChildrenLayout`: ``BULLET`` coalesces consecutive
  text siblings into a :class:`~panflute.BulletList`, ``NUMBERED`` into a
  :class:`~panflute.OrderedList`, and ``DOCUMENT`` renders them as flowing
  :class:`~panflute.Para` blocks.  Text containing a fenced code block is parsed
  at block level so the fence becomes a :class:`~panflute.CodeBlock`.
- :class:`~guffin.vertex.ImageVertex` — embedded as a :class:`~panflute.Image`
  element pointing at the local path from *image_files*; falls back to a
  :class:`~panflute.Link` when *image_files* has no entry for the vertex.
- :class:`~guffin.vertex.CodeBlockVertex` — rendered as a
  :class:`~panflute.CodeBlock` whose class is the vertex's language, so Pandoc
  applies language-specific syntax highlighting.

Public symbols:

- :func:`strip_links` — unwrap every Link in a run of inlines to its display-text
  content, reducing the run to plain (link-free) inlines.
- :func:`parse_inline_md` — batch-parse Pandoc Markdown inline text strings into
  panflute inline element lists via a single Pandoc call.
- :func:`parse_block_md` — parse a single Pandoc Markdown string into panflute
  block elements, preserving block constructs such as fenced code blocks.
- :func:`build_inline_map` — collect all text strings from a
  :class:`~guffin.vertex_tree.VertexTree` and return the parsed inline element
  map via :func:`parse_inline_md`.
- :func:`build_child_blocks` — convert an ordered list of vertex UIDs to Pandoc
  block elements.
- :func:`vertex_tree_to_pandoc` — convert a
  :class:`~guffin.vertex_tree.VertexTree` to a Panflute :class:`~panflute.Doc`.
- :data:`InlineMap` — type alias for the ``str → list[pf.Inline]`` mapping produced by
  :func:`build_inline_map` and returned alongside the :class:`~panflute.Doc` by
  :func:`vertex_tree_to_pandoc`.
- :data:`VertexLinkResolver` — type alias for the resolver callable accepted by
  :func:`resolve_vertex_links`.
- :func:`make_resolver` — build a :data:`VertexLinkResolver` that renders each
  ``x-guffin`` link as its destination vertex's own converted content.
- :func:`resolve_vertex_links` — walk a :class:`~panflute.Doc` in place and replace
  ``x-guffin`` :class:`~panflute.Link` elements using a caller-supplied resolver.
- :func:`pandoc_to_json` — serialize a Panflute :class:`~panflute.Doc` to a
  Pandoc JSON string, optionally writing it to a file for debugging.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

from collections.abc import Callable
from io import StringIO
import logging
import uuid

from pathlib import Path
from typing import Final

import regex
import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from pydantic import ConfigDict, validate_call

from guffin.common.geometry import ImageSize
from guffin.common.table import HAlign
from guffin.model.vertex import (
    BlockEmbedVertex,
    BlockQuoteVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
    VertexChildren,
)
from guffin.model.vertex_tree import VertexTree, root_vertex
from guffin.model.view import ChildrenLayout, VertexView, ViewMap
from guffin.model.link import VertexLink, VertexLinkKind, parse_vertex_link
from guffin.roam.primitives import Uid

logger = logging.getLogger(__name__)

type InlineMap = dict[str, list[pf.Inline]]
"""Mapping from Pandoc Markdown text string to its parsed panflute inline elements."""

_DEFAULT_VIEW: Final[VertexView] = VertexView()
"""Fallback :class:`~guffin.model.view.VertexView` for a vertex absent from the view map."""


def _children_layout(uid: Uid, view_map: ViewMap) -> ChildrenLayout:
    """Return the :class:`~guffin.model.view.ChildrenLayout` governing *uid*'s children."""
    return view_map.get(uid, _DEFAULT_VIEW).children_layout


type VertexLinkResolver = Callable[[VertexLink, Vertex, list[pf.Inline]], list[pf.Inline]]
"""Resolver: (parsed link, destination vertex, original display inlines) → replacement inlines."""

# A fenced code block, after Roam→Pandoc normalization, opens with a ``` fence
# at the start of a line.  Its presence in a text field signals that the field
# must be parsed as block-level Markdown rather than inline.
_CONTAINS_CODE_BLOCK_RE: Final[regex.Pattern[str]] = regex.compile(r"(?m)^```")


def strip_links(inlines: list[pf.Inline]) -> list[pf.Inline]:
    """Return *inlines* with every Link replaced by its display-text content.

    Unwraps each :class:`~panflute.Link` to its inner content inlines, preserving
    the display text while discarding the hyperlink target.  Useful wherever a
    run of inlines must be reduced to plain text — e.g. sanitizing metadata
    fields (such as the document title) where Pandoc's Typst writer would embed a
    ``#link("url")[text]`` call inside a double-quoted Typst string and break the
    parser, or flattening a page title that itself contains a nested reference.

    Args:
        inlines: Panflute inline elements to filter.

    Returns:
        A new list with Link elements unwrapped to their content inlines.
    """
    result: list[pf.Inline] = []
    for inline in inlines:
        if isinstance(inline, pf.Link):
            result.extend(list(inline.content))
        else:
            result.append(inline)
    return result


def _extract_bg_color(inlines: list[pf.Inline]) -> tuple[str, list[pf.Inline]] | None:
    """Return ``(color, inner_inlines)`` when *inlines* is a single bg-color Span.

    A whole-line background color block is signalled by a single
    :class:`~panflute.Span` with a ``bg-color`` attribute, produced by
    :func:`~guffin.pipeline.roam_md_to_pandoc_md.convert_bg_color_line`.  When that
    pattern is detected the span is unwrapped so the caller can promote the
    enclosing block to a :class:`~panflute.Div`.

    Args:
        inlines: Parsed panflute inline elements for a single text field.

    Returns:
        A ``(color, inner_inlines)`` tuple if *inlines* is exactly one
        ``Span`` carrying a ``bg-color`` attribute, otherwise ``None``.
    """
    if len(inlines) == 1 and isinstance(inlines[0], pf.Span):
        color: str | None = inlines[0].attributes.get("bg-color")
        if color:
            return color, list(inlines[0].content)
    return None


# ---------------------------------------------------------------------------
# Inline Pandoc Markdown parsing
# ---------------------------------------------------------------------------


@validate_call
def parse_inline_md(texts: list[str]) -> InlineMap:
    """Batch-parse Pandoc Markdown inline text strings into panflute inline element lists.

    Each parse requires a Pandoc subprocess, so parsing text fields one at a
    time would spawn one subprocess per block.  Batching every unique string
    into a single call amortizes that cost across the whole document.

    Joins all unique, non-empty strings with a random sentinel paragraph as
    separator, converts the combined document to Pandoc JSON in a single
    subprocess call, then maps each input string back to the inline elements
    from its corresponding paragraph block.

    Text strings that produce no paragraph block (e.g. bare ``---``, which
    Pandoc parses as a thematic break) are absent from the returned mapping;
    callers should fall back to ``[pf.Str(text)]`` for missing entries.

    Args:
        texts: Text strings to parse.  Duplicates and empty strings are
            silently deduplicated / ignored.

    Returns:
        Mapping from each unique non-empty input string to the list of
        panflute inline elements produced by parsing it as Pandoc Markdown.
    """
    unique: Final[list[str]] = list(dict.fromkeys(t for t in texts if t))
    if not unique:
        return {}

    # Random sentinel used as a paragraph separator between entries.
    # UUID hex makes collision with real content effectively impossible.
    sep: Final[str] = f"GUFFIN_SEP_{uuid.uuid4().hex}"
    combined: Final[str] = f"\n\n{sep}\n\n".join(unique)

    json_str: Final[str] = pypandoc.convert_text(combined, "json", format="markdown")
    doc: Final[pf.Doc] = pf.load(StringIO(json_str))

    result: Final[InlineMap] = {}
    text_idx: int = 0

    for block in doc.content:  # `block: pf.Block`
        if text_idx >= len(unique):
            break
        block_inlines: list[pf.Inline] = list(block.content) if hasattr(block, "content") else []
        # Sentinel paragraph → advance to the next text entry.
        if (
            isinstance(block, pf.Para)
            and len(block_inlines) == 1
            and isinstance(block_inlines[0], pf.Str)
            and block_inlines[0].text == sep
        ):
            text_idx += 1
            continue
        # First Para or Plain block for the current text → record its inlines.
        if isinstance(block, (pf.Para, pf.Plain)) and unique[text_idx] not in result:
            result[unique[text_idx]] = block_inlines

    return result


@validate_call
def parse_block_md(text: str) -> list[pf.Block]:
    """Parse a single Pandoc Markdown string into a list of panflute block elements.

    Unlike :func:`parse_inline_md`, this performs a full block-level parse, so
    block constructs such as fenced code blocks are preserved as their
    corresponding panflute block elements (e.g. :class:`~panflute.CodeBlock`)
    rather than being flattened into inline content.

    Args:
        text: The Pandoc Markdown text to parse.

    Returns:
        The list of :class:`~panflute.Block` elements produced by parsing
        *text*.
    """
    json_str: Final[str] = pypandoc.convert_text(text, "json", format="markdown")
    doc: Final[pf.Doc] = pf.load(StringIO(json_str))
    return list(doc.content)


# ---------------------------------------------------------------------------
# Pandoc document building
# ---------------------------------------------------------------------------


# Vertex types whose natural rendering is one or more Pandoc Blocks that cannot be
# faithfully represented as inline content.  A reference whose entire content targets
# one of these must be rendered as the referenced block(s), not via the inline link
# resolver.  The remaining ref-able types (PageVertex, HeadingVertex, TextVertex) are
# inline-representable and stay on the inline resolution path.
_BLOCK_LEVEL_VERTEX_TYPES: Final[tuple[type[Vertex], ...]] = (
    ImageVertex,
    CodeBlockVertex,
    CalloutVertex,
    BlockQuoteVertex,
    TableVertex,
)


def _block_ref_target(
    vertex: TextVertex,
    vertex_tree: VertexTree,
    inline_map: InlineMap,
) -> Vertex | None:
    """Return the destination vertex when *vertex* is solely a reference to a block-level one.

    Block-level vertices (see :data:`_BLOCK_LEVEL_VERTEX_TYPES` — e.g. code blocks,
    images, tables) render as Pandoc Blocks and cannot be represented as the inline
    content of a list item or paragraph.  When a text vertex's entire parsed content is
    a single ``x-guffin`` link whose destination is such a vertex, that destination is
    returned so the reference can be rendered identically to the referenced block rather
    than degraded to an inline link.

    Args:
        vertex: The text-content vertex to inspect.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        inline_map: Mapping from text string to parsed panflute inline elements.

    Returns:
        The referenced block-level :data:`~guffin.vertex.Vertex`, or ``None`` in every
        other case — including a reference to an inline-representable vertex, or one
        mixed with surrounding text, both of which are resolved inline instead.
    """
    inlines: Final[list[pf.Inline] | None] = inline_map.get(vertex.text)
    if inlines is None or len(inlines) != 1 or not isinstance(inlines[0], pf.Link):
        return None
    vertex_link: Final[VertexLink | None] = parse_vertex_link(inlines[0].url)
    if vertex_link is None:
        return None
    dest: Final[Vertex | None] = vertex_tree.uid_map.get(vertex_link.uid)
    return dest if isinstance(dest, _BLOCK_LEVEL_VERTEX_TYPES) else None


def _build_list_item(
    vertex: TextVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> pf.ListItem:
    """Build a Pandoc :class:`~panflute.ListItem` from a :class:`~guffin.vertex.TextVertex`.

    The item body is a :class:`~panflute.Plain` inline block, or — when the
    vertex text contains a fenced code block — the block elements produced by a
    full block-level parse via :func:`parse_block_md`.  If the vertex has
    children they are rendered recursively via :func:`build_child_blocks` using the
    vertex's own children layout, and appended as nested blocks inside the item.

    Args:
        vertex: The text-content vertex to render as a list item.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex* (≥ 2 when this function is called).

    Returns:
        A :class:`~panflute.ListItem` wrapping the vertex text and any
        nested children.
    """
    content: list[pf.Block]
    if _CONTAINS_CODE_BLOCK_RE.search(vertex.text):
        content = parse_block_md(vertex.text)
    else:
        inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
        bg: Final[tuple[str, list[pf.Inline]] | None] = _extract_bg_color(inlines)
        if bg is not None:
            bg_color, inner = bg
            content = [pf.Div(pf.Plain(*inner), attributes={"bg-color": bg_color})]
        else:
            content = [pf.Plain(*inlines)]
    if vertex.children:
        content.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return pf.ListItem(*content)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def build_child_blocks(
    child_uids: VertexChildren,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    layout: ChildrenLayout,
    depth: int,
) -> list[pf.Block]:
    """Build a list of Pandoc block elements from an ordered list of child UIDs.

    The children's parent supplies *layout* (its
    :class:`~guffin.model.view.ChildrenLayout`), which governs how consecutive
    :class:`~guffin.vertex.TextVertex` siblings are wrapped:

    - :attr:`~guffin.model.view.ChildrenLayout.BULLET` — coalesced into a single
      :class:`~panflute.BulletList`.
    - :attr:`~guffin.model.view.ChildrenLayout.NUMBERED` — coalesced into a single
      :class:`~panflute.OrderedList`.
    - :attr:`~guffin.model.view.ChildrenLayout.DOCUMENT` — rendered as flowing blocks
      (paragraphs) via :func:`_vertex_to_blocks`, with no list wrapper.

    Any non-text vertex flushes the pending list and is rendered via
    :func:`_vertex_to_blocks` regardless of *layout*.  A text vertex that is solely a
    reference to a block-level vertex (see :func:`_block_ref_target`) is likewise flushed
    and rendered as the referenced block, so it appears identically to the block it
    references.  Each vertex's own children are rendered using *its* layout (looked up in
    *view_map*).

    Unknown UIDs (absent from *vertex_tree*) are skipped with a warning.

    Args:
        child_uids: Ordered list of child UIDs to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        layout: The layout governing how *child_uids* are wrapped (their parent's layout).
        depth: Tree depth of the children (1 = direct children of the page root).

    Returns:
        A flat list of :class:`~panflute.Block` elements representing the
        rendered children, with consecutive text vertices grouped into a
        :class:`~panflute.BulletList` or :class:`~panflute.OrderedList` per *layout*.
    """
    result: Final[list[pf.Block]] = []
    pending_items: Final[list[pf.ListItem]] = []

    def flush_pending() -> None:
        """Wrap any pending list items in an ordered or bulleted list per *layout*."""
        if pending_items:
            wrapped: pf.Block = (
                pf.OrderedList(*pending_items) if layout is ChildrenLayout.NUMBERED else pf.BulletList(*pending_items)
            )
            result.append(wrapped)
            pending_items.clear()

    for uid in child_uids:
        if uid not in vertex_tree.uid_map:
            logger.warning("child uid=%r not found in vertex_tree; skipping", uid)
            continue
        vertex: Vertex = vertex_tree.uid_map[uid]
        ref_target: Vertex | None = (
            _block_ref_target(vertex, vertex_tree, inline_map) if isinstance(vertex, TextVertex) else None
        )
        if ref_target is not None:
            # A block whose entire content references a block-level vertex renders as that
            # referenced block — never wrapped in a list item.
            flush_pending()
            result.extend(_vertex_to_blocks(ref_target, vertex_tree, image_files, inline_map, view_map, depth))
            if isinstance(vertex, TextVertex) and vertex.children:
                result.extend(
                    build_child_blocks(
                        vertex.children,
                        vertex_tree,
                        image_files,
                        inline_map,
                        view_map,
                        _children_layout(vertex.uid, view_map),
                        depth + 1,
                    )
                )
        elif isinstance(vertex, TextVertex) and layout is not ChildrenLayout.DOCUMENT:
            pending_items.append(_build_list_item(vertex, vertex_tree, image_files, inline_map, view_map, depth))
        else:
            flush_pending()
            result.extend(_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth))

    flush_pending()
    return result


def _page_vertex_to_blocks(
    vertex: PageVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.PageVertex` to Pandoc block elements.

    Delegates to :func:`build_child_blocks` at depth 1 using the page's own children
    layout, so a page with a ``BULLET`` layout renders its top-level children as a
    bulleted outline.  The page title is handled separately by :func:`vertex_tree_to_pandoc`.

    Args:
        vertex: The page vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.

    Returns:
        Block elements for the page's children, rendered at depth 1.
    """
    return build_child_blocks(
        vertex.children or [],
        vertex_tree,
        image_files,
        inline_map,
        view_map,
        _children_layout(vertex.uid, view_map),
        1,
    )


def _heading_vertex_to_blocks(
    vertex: HeadingVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.HeadingVertex` to Pandoc block elements.

    Produces one :class:`~panflute.Header` at the vertex's heading level,
    followed by the recursively rendered children (laid out per the heading's
    own children layout).

    Args:
        vertex: The heading vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex*.

    Returns:
        A :class:`~panflute.Header` block followed by any child blocks.
    """
    inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
    blocks: list[pf.Block] = [pf.Header(*inlines, level=vertex.heading_level)]
    if vertex.children:
        blocks.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return blocks


def _text_vertex_to_blocks(
    vertex: TextVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.TextVertex` to flowing (document) block elements.

    Produces one :class:`~panflute.Para` — or the block elements from a full block-level
    parse via :func:`parse_block_md` when the text contains a fenced code block — followed
    by the recursively rendered children laid out per the vertex's own children layout.

    This always renders the bare, document-flow form; whether the vertex is *itself* wrapped
    in a bullet/numbered list item is decided by :func:`build_child_blocks` from the parent's
    layout, so this function is reached only for the unwrapped (document-layout or
    transcluded) case.

    Args:
        vertex: The text-content vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex* (1 = direct page child).

    Returns:
        A :class:`~panflute.Para` (or block-parsed elements) followed by any child blocks.
    """
    para_blocks: list[pf.Block]
    if _CONTAINS_CODE_BLOCK_RE.search(vertex.text):
        para_blocks = parse_block_md(vertex.text)
    else:
        text_inlines: Final[list[pf.Inline]] = inline_map.get(vertex.text, [pf.Str(vertex.text)])
        bg: Final[tuple[str, list[pf.Inline]] | None] = _extract_bg_color(text_inlines)
        if bg is not None:
            bg_color, inner = bg
            para_blocks = [pf.Div(pf.Para(*inner), attributes={"bg-color": bg_color})]
        else:
            para_blocks = [pf.Para(*text_inlines)]
    if vertex.children:
        para_blocks.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return para_blocks


def _image_vertex_to_blocks(
    vertex: ImageVertex,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
) -> list[pf.Block]:
    """Render an :class:`~guffin.vertex.ImageVertex` to Pandoc block elements.

    Produces a :class:`~panflute.Para` containing a :class:`~panflute.Image`
    if the asset was fetched, or a :class:`~panflute.Link` fallback otherwise.

    Args:
        vertex: The image vertex to render.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.

    Returns:
        A :class:`~panflute.Para` wrapping either an embedded image or a
        hyperlink fallback.
    """
    img_path: Path | None = image_files.get(vertex.uid)
    if img_path is not None:
        alt: Final[list[pf.Inline]] = (
            inline_map.get(vertex.alt_text, [pf.Str(vertex.alt_text)]) if vertex.alt_text else []
        )
        attrs: Final[dict[str, str]] = {}
        size: Final[ImageSize] = vertex.scaled_image_size
        if size.width is not None or size.height is not None:
            if size.width is not None:
                attrs["width"] = str(size.width)
            if size.height is not None:
                attrs["height"] = str(size.height)
        img: Final[pf.Image] = pf.Image(*alt, url=str(img_path), title=vertex.file_name or "", attributes=attrs)
        return [pf.Para(img)]
    else:
        label_text: Final[str] = vertex.alt_text or vertex.file_name or str(vertex.source)
        label: Final[list[pf.Inline]] = inline_map.get(label_text, [pf.Str(label_text)])
        link: Final[pf.Link] = pf.Link(*label, url=str(vertex.source))
        logger.warning("Image uid=%r not fetched; rendering as link", vertex.uid)
        return [pf.Para(link)]


def _callout_vertex_to_blocks(
    vertex: CalloutVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.CalloutVertex` to Pandoc block elements.

    Produces a :class:`~panflute.Div` with classes ``["callout",
    "callout-{type}"]`` where *type* is the lowercased
    :class:`~guffin.vertex.CalloutVertex.CalloutType` value (one of the
    twelve recognised keywords: ``info``, ``note``, ``quote``, ``example``,
    ``summary``, ``question``, ``tip``, ``success``, ``warning``,
    ``danger``, ``failure``, ``bug``).  When a title is present, the first
    child is a ``callout-title`` :class:`~panflute.Div` whose content is a
    :class:`~panflute.Para` with the parsed inline elements.  The body
    (if any) is re-parsed as block-level Markdown and appended as sibling
    blocks inside the outer :class:`~panflute.Div`.  Child vertex blocks
    follow at the end.

    Output-format-specific transformation is applied by a Lua filter in
    the respective rendering module (GFM blockquote alert syntax or Typst
    ``gentle-clues`` callout boxes).

    Args:
        vertex: The callout vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex*.

    Returns:
        A single-element list containing the :class:`~panflute.Div`.
    """
    callout_type: Final[str] = vertex.callout_type.value.lower()
    callout_blocks: list[pf.Block] = []
    if vertex.title:
        title_inlines: Final[list[pf.Inline]] = inline_map.get(vertex.title, [pf.Str(vertex.title)])
        callout_blocks.append(pf.Div(pf.Para(*title_inlines), classes=["callout-title"]))
    if vertex.body:
        # Insert blank lines at block-type boundaries except between consecutive
        # list items (which would create a loose list with unwanted inter-item spacing).
        body_lines: Final[list[str]] = vertex.body.splitlines()
        joined_lines: list[str] = []
        for i, line in enumerate(body_lines):
            if i > 0:
                prev_is_list: bool = body_lines[i - 1].startswith(("- ", "* ", "+ "))
                curr_is_list: bool = line.startswith(("- ", "* ", "+ "))
                if not (prev_is_list and curr_is_list):
                    joined_lines.append("")
            joined_lines.append(line)
        body_json: Final[str] = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            "\n".join(joined_lines), "json", format="markdown"
        )
        body_doc: Final[pf.Doc] = pf.load(StringIO(body_json))
        callout_blocks.extend(list(body_doc.content))
    if vertex.children:
        callout_blocks.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return [pf.Div(*callout_blocks, classes=["callout", f"callout-{callout_type}"])]


def _code_block_vertex_to_blocks(vertex: CodeBlockVertex) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.CodeBlockVertex` to a Pandoc :class:`~panflute.CodeBlock`.

    The vertex's :attr:`~guffin.vertex.CodeBlockVertex.language` is set as the
    code block's class, which Pandoc uses to apply language-specific syntax
    highlighting in the output.  The code content is emitted verbatim.

    Args:
        vertex: The code block vertex to render.

    Returns:
        A single-element list containing the :class:`~panflute.CodeBlock`.
    """
    return [pf.CodeBlock(vertex.code, classes=[vertex.language.value])]


def _block_quote_vertex_to_blocks(
    vertex: BlockQuoteVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Render a :class:`~guffin.vertex.BlockQuoteVertex` to a Pandoc :class:`~panflute.BlockQuote`.

    The vertex text is parsed at block level via :func:`parse_block_md` so that
    multi-paragraph content and embedded list items are preserved as distinct block
    elements inside the :class:`~panflute.BlockQuote`.  Child vertices are rendered
    recursively and appended inside the same :class:`~panflute.BlockQuote`.

    Args:
        vertex: The block-quote vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex*.

    Returns:
        A single-element list containing the :class:`~panflute.BlockQuote`.
    """
    inner_blocks: list[pf.Block] = parse_block_md(vertex.text.replace("\n", "\n\n"))
    if vertex.children:
        inner_blocks.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return [pf.BlockQuote(*inner_blocks)]


def _halign_to_pandoc_str(align: HAlign) -> str:
    """Return the Panflute/Pandoc alignment string for *align*."""
    match align:
        case HAlign.LEFT:
            return "AlignLeft"
        case HAlign.CENTER:
            return "AlignCenter"
        case HAlign.RIGHT:
            return "AlignRight"


def _table_vertex_to_blocks(
    vertex: TableVertex,
    inline_map: InlineMap,
) -> list[pf.Block]:
    """Render *vertex* as a Panflute :class:`~panflute.Table`.

    The first row becomes the :class:`~panflute.TableHead` when
    :attr:`~guffin.common.table.Table.has_row_header` is ``True``; otherwise
    the head is empty and all rows go into the :class:`~panflute.TableBody`.
    When :attr:`~guffin.common.table.Table.has_col_header` is ``True``,
    ``row_head_columns=1`` is set on the :class:`~panflute.TableBody` so Pandoc
    treats the first column as a row-header column.

    Cell alignment is resolved via
    :meth:`~guffin.common.table.TableStyle.style_for` and mapped to Pandoc
    alignment strings.  Column widths are left as ``'ColWidthDefault'``
    (auto-sized by Pandoc).

    Args:
        vertex: The table vertex to render.
        inline_map: Mapping from cell text to parsed panflute inline elements.

    Returns:
        A single-element list containing the :class:`~panflute.Table` block.
    """
    table = vertex.table
    style = vertex.table_style
    num_cols: Final[int] = table.num_cols
    colspec: Final[list[tuple[str, str]]] = [("AlignDefault", "ColWidthDefault")] * num_cols
    row_head_cols: Final[int] = 1 if table.has_col_header else 0

    def make_cell(row_idx: int, col_idx: int) -> pf.TableCell:
        cell_text = table.rows[row_idx][col_idx]
        cell_style = style.style_for(row_idx, col_idx, table)
        inlines = inline_map.get(cell_text, [pf.Str(cell_text)])
        return pf.TableCell(pf.Plain(*inlines), alignment=_halign_to_pandoc_str(cell_style.align))

    def make_row(row_idx: int) -> pf.TableRow:
        return pf.TableRow(*[make_cell(row_idx, col) for col in range(num_cols)])

    if table.has_row_header:
        head = pf.TableHead(make_row(0))
        body = pf.TableBody(*[make_row(row) for row in range(1, table.num_rows)], row_head_columns=row_head_cols)
    else:
        head = pf.TableHead()
        body = pf.TableBody(*[make_row(row) for row in range(table.num_rows)], row_head_columns=row_head_cols)

    return [pf.Table(body, head=head, foot=pf.TableFoot(), colspec=colspec)]


def _block_embed_vertex_to_blocks(
    vertex: BlockEmbedVertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Render a block embed by transcluding the embedded vertex's blocks in place.

    Looks up the embed target (:attr:`~guffin.vertex.BlockEmbedVertex.vertex_link`'s UID) in
    *vertex_tree* and renders its full subtree via :func:`_vertex_to_blocks`, so a
    ``{{embed: ((<uid>))}}`` block reproduces the referenced block and its descendants.  Any
    children of the embed block itself are rendered after the transcluded content.  When the
    target is absent from *vertex_tree*, the embed renders nothing and a warning is logged.

    Args:
        vertex: The block-embed vertex to render.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex*.

    Returns:
        The transcluded target's block elements, followed by the embed's own child blocks.
    """
    target: Final[Vertex | None] = vertex_tree.uid_map.get(vertex.vertex_link.uid)
    if target is None:
        logger.warning(
            "block embed uid=%r target uid=%r not found in vertex_tree; rendering nothing",
            vertex.uid,
            vertex.vertex_link.uid,
        )
        return []
    blocks: Final[list[pf.Block]] = list(
        _vertex_to_blocks(target, vertex_tree, image_files, inline_map, view_map, depth)
    )
    if vertex.children:
        blocks.extend(
            build_child_blocks(
                vertex.children,
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(vertex.uid, view_map),
                depth + 1,
            )
        )
    return blocks


def _vertex_to_blocks(
    vertex: Vertex,
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    inline_map: InlineMap,
    view_map: ViewMap,
    depth: int,
) -> list[pf.Block]:
    """Dispatch a single :data:`~guffin.vertex.Vertex` to its type-specific rendering function.

    Args:
        vertex: The vertex to convert.
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` providing the UID-to-vertex lookup.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            local image file path.
        inline_map: Mapping from text string to parsed panflute inline elements.
        view_map: Presentation view map keyed by vertex uid, governing child layout.
        depth: Tree depth of *vertex* (0 = root, 1 = direct page child, …).

    Returns:
        A list of :class:`~panflute.Block` elements representing *vertex*
        and its subtree.
    """
    match vertex:
        case PageVertex():
            return _page_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map)
        case HeadingVertex():
            return _heading_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth)
        case TextVertex():
            return _text_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth)
        case ImageVertex():
            return _image_vertex_to_blocks(vertex, image_files, inline_map)
        case CalloutVertex():
            return _callout_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth)
        case CodeBlockVertex():
            return _code_block_vertex_to_blocks(vertex)
        case BlockQuoteVertex():
            return _block_quote_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth)
        case TableVertex():
            return _table_vertex_to_blocks(vertex, inline_map)
        case BlockEmbedVertex():
            return _block_embed_vertex_to_blocks(vertex, vertex_tree, image_files, inline_map, view_map, depth)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def build_inline_map(vertex_tree: VertexTree) -> InlineMap:
    """Collect all text strings from *vertex_tree* and return their parsed inline elements.

    Gathers every text string that requires inline Pandoc Markdown parsing —
    page titles, heading text, block text, image alt text, callout titles, and
    table cell text — across both :attr:`~guffin.vertex_tree.VertexTree.tree_vertices`
    and :attr:`~guffin.vertex_tree.VertexTree.ref_vertices`, then delegates to
    :func:`parse_inline_md` for a single batch Pandoc subprocess call.  Including
    the referenced (stub) vertices ensures the title or text used as a link's
    display label is available pre-parsed when an ``x-guffin`` link resolves to a
    referenced vertex.

    Args:
        vertex_tree: The vertex tree whose text strings are to be parsed.

    Returns:
        Mapping from each unique text string to its parsed panflute inline
        elements.  Strings absent from the mapping (e.g. bare ``---``) should
        fall back to ``[pf.Str(text)]``.
    """
    texts: Final[list[str]] = []
    for vertex in (*vertex_tree.tree_vertices, *vertex_tree.ref_vertices):
        match vertex:
            case PageVertex(title=t):
                texts.append(t)
            case HeadingVertex(text=t):
                texts.append(t)
            case TextVertex(text=t):
                texts.append(t)
            case ImageVertex(alt_text=t) if t is not None:
                texts.append(t)
            case CalloutVertex(title=t) if t:
                texts.append(t)
            case TableVertex():
                for row in vertex.table.rows:
                    texts.extend(row)
            case _:
                pass
    return parse_inline_md(texts)


@validate_call
def vertex_tree_to_pandoc(
    vertex_tree: VertexTree,
    image_files: dict[Uid, Path],
    view_map: ViewMap,
    *,
    title_in_header: bool = False,
) -> tuple[pf.Doc, InlineMap]:
    """Convert a :class:`~guffin.vertex_tree.VertexTree` to a Panflute :class:`~panflute.Doc`.

    Collects all text strings from the tree, parses their inline Pandoc Markdown
    in a single Pandoc call, then walks the tree to build Pandoc block
    elements.

    The *title_in_header* flag controls how a root
    :class:`~guffin.vertex.PageVertex` title is rendered:

    - ``False`` (default, PDF path) — title stored as the Pandoc metadata
      ``title`` field; children rendered as body blocks.
    - ``True`` (Markdown path) — title rendered as a level-1
      :class:`~panflute.Header` prepended to the body blocks; no metadata.

    Args:
        vertex_tree: The normalized vertex tree to convert.
        image_files: Mapping from :class:`~guffin.vertex.ImageVertex` UID to
            the local :class:`~pathlib.Path` of the fetched image file.
            Vertices absent from this mapping fall back to hyperlinks.
            Pass relative :class:`~pathlib.Path` values (e.g.
            ``Path(filename)``) when the output is Markdown, so that image
            references in the rendered document are relative rather than
            absolute.
        view_map: Presentation view map keyed by vertex uid; governs how each
            vertex's children are laid out (bulleted/numbered/document).
        title_in_header: When ``True``, render a root
            :class:`~guffin.vertex.PageVertex` title as an H1 header instead
            of storing it in document metadata.  Defaults to ``False``.

    Returns:
        A two-tuple of the :class:`~panflute.Doc` ready for serialization via
        :func:`panflute.dump` and the :func:`build_inline_map` mapping used
        during construction (passed to vertex-link resolvers so they can look
        up pre-parsed inlines by text string).
    """
    root: Final[Vertex] = root_vertex(vertex_tree)
    inline_map: Final[InlineMap] = build_inline_map(vertex_tree)

    metadata: dict[str, pf.MetaValue] = {}
    blocks: list[pf.Block] = []

    if isinstance(root, PageVertex):
        title_inlines: Final[list[pf.Inline]] = inline_map.get(root.title, [pf.Str(root.title)])
        if title_in_header:
            blocks.append(pf.Header(*title_inlines, level=1))
        else:
            metadata["title"] = pf.MetaInlines(*strip_links(list(title_inlines)))
        blocks.extend(
            build_child_blocks(
                root.children or [],
                vertex_tree,
                image_files,
                inline_map,
                view_map,
                _children_layout(root.uid, view_map),
                depth=1,
            )
        )
    else:
        blocks.extend(_vertex_to_blocks(root, vertex_tree, image_files, inline_map, view_map, depth=0))

    return pf.Doc(*blocks, metadata=metadata), inline_map


def make_resolver(inline_map: InlineMap) -> VertexLinkResolver:
    """Build a :data:`VertexLinkResolver` that renders each link as its destination's content.

    The returned resolver maps an ``x-guffin`` link's destination vertex to replacement
    inlines, ignoring the link's own display text in favour of the destination's already
    converted content (looked up in *inline_map*).  This is what makes a block reference
    render identically to the block it points at — including Color Highlighter spans and
    other inline markup — rather than echoing the raw reference text.

    Per destination type:

    - :class:`~guffin.vertex.PageVertex` — the page title, with any nested reference
      flattened to plain text via :func:`strip_links`.
    - :class:`~guffin.vertex.HeadingVertex`, :class:`~guffin.vertex.TextVertex`,
      :class:`~guffin.vertex.BlockQuoteVertex` — the destination's converted text inlines.
    - :class:`~guffin.vertex.ImageVertex` — an inline :class:`~panflute.Image` for an
      embed, otherwise a :class:`~panflute.Link` to the image source.
    - :class:`~guffin.vertex.CodeBlockVertex` — inline :class:`~panflute.Code` (a
      block-level code reference is handled earlier, in :func:`build_child_blocks`).
    - :class:`~guffin.vertex.CalloutVertex`, :class:`~guffin.vertex.TableVertex` — the
      original display inlines (no inline-representable substitute).

    Args:
        inline_map: Mapping from text string to parsed panflute inline elements, used to
            look up a destination vertex's converted content.

    Returns:
        A resolver callable suitable for :func:`resolve_vertex_links`.
    """

    def _resolve(vertex_link: VertexLink, vertex: Vertex, display: list[pf.Inline]) -> list[pf.Inline]:
        match vertex:
            case PageVertex():
                # The title is raw Pandoc Markdown that may itself contain a nested
                # reference (an x-guffin link); parse it and flatten any such link to
                # plain display text so the page reference renders as its bare title.
                return strip_links(inline_map.get(vertex.title, [pf.Str(vertex.title)]))
            case HeadingVertex():
                return inline_map.get(vertex.text, [pf.Str(vertex.text)])
            case TextVertex():
                return inline_map.get(vertex.text, [pf.Str(vertex.text)])
            case ImageVertex() if vertex_link.kind == VertexLinkKind.EMBED:
                return [pf.Image(*display, url=str(vertex.source), title="")]
            case ImageVertex():
                return [pf.Link(*display, url=str(vertex.source))]
            case CodeBlockVertex():
                return [pf.Code(vertex.code, classes=[vertex.language.value])]
            case CalloutVertex():
                return display
            case BlockQuoteVertex():
                return inline_map.get(vertex.text, [pf.Str(vertex.text)])
            case TableVertex():
                return display
            case BlockEmbedVertex():
                return display

    return _resolve


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def resolve_vertex_links(
    doc: pf.Doc,
    vertex_tree: VertexTree,
    resolver: VertexLinkResolver,
) -> None:
    """Walk *doc* in place and replace every ``x-guffin`` Link with resolver-produced inlines.

    For each :class:`~panflute.Link` whose URL is a well-formed ``x-guffin``
    vertex link (see :mod:`~guffin.link`), looks up the destination vertex in
    *vertex_tree* and calls *resolver* with the parsed :class:`~guffin.link.VertexLink`,
    the destination :class:`~guffin.vertex.Vertex`, and the original link's
    display-text inlines.  The inlines returned by *resolver* replace the Link
    in the document tree.

    When a destination UID is absent from *vertex_tree* — e.g. a reference to a block
    whose own vertex could not be transcribed and was dropped, such as an external
    ``{{table}}`` whose cells were not fetched — the Link is left as its display-text
    inlines and a warning is logged, rather than failing the whole export.

    Mutates *doc* in place via :meth:`~panflute.Element.walk`; does not return
    a new document.

    Args:
        doc: The Panflute document to walk and modify.
        vertex_tree: Provides the UID-to-vertex lookup for resolving link destinations.
        resolver: Invoked for each x-guffin Link whose destination vertex is present
            in *vertex_tree*; receives the parsed link, the destination vertex, and
            the original display-text inlines; returns replacement inline elements.
    """

    def _action(elem: pf.Element, doc: pf.Doc) -> list[pf.Inline] | None:
        if not isinstance(elem, pf.Link):
            return None
        vertex_link: Final[VertexLink | None] = parse_vertex_link(elem.url)
        if vertex_link is None:
            return None
        display: Final[list[pf.Inline]] = list(elem.content)
        if vertex_link.uid not in vertex_tree.uid_map:
            logger.warning("x-guffin link uid=%r not found in vertex_tree; leaving display text", vertex_link.uid)
            return display
        dest: Final[Vertex] = vertex_tree.uid_map[vertex_link.uid]
        return resolver(vertex_link, dest, display)

    doc.walk(_action)


def pandoc_to_json(
    doc: pf.Doc,
    dump_pandoc_ast: bool = False,
    ast_dump_dir: Path | None = None,
    ast_dump_stem: str | None = None,
) -> str:
    """Serialize *doc* to a Pandoc JSON string.

    Dumps *doc* via :func:`panflute.dump` and returns the resulting JSON
    string.  When *dump_pandoc_ast* is ``True`` and both *ast_dump_dir* and
    *ast_dump_stem* are provided, the JSON is also written to
    ``<ast_dump_dir>/<ast_dump_stem>.pandoc.json`` before being returned —
    useful for inspecting the intermediate Pandoc AST without modifying the
    main rendering pipeline.

    Args:
        doc: The Panflute document to serialize.
        dump_pandoc_ast: When ``True``, write the JSON to disk alongside the
            primary output.  Requires *ast_dump_dir* and *ast_dump_stem*.
        ast_dump_dir: Directory in which to write the ``.pandoc.json`` file.
            Ignored when *dump_pandoc_ast* is ``False``.
        ast_dump_stem: POSIX-normalized filename stem (no extension) used to
            construct the dump filename.  Ignored when *dump_pandoc_ast* is
            ``False``.

    Returns:
        The Pandoc JSON representation of *doc*.
    """
    buf: Final[StringIO] = StringIO()
    pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
    json_str: Final[str] = buf.getvalue()
    if dump_pandoc_ast and ast_dump_dir is not None and ast_dump_stem is not None:
        ast_dump_path: Final[Path] = ast_dump_dir / f"{ast_dump_stem}.pandoc.json"
        ast_dump_path.write_text(json_str, encoding="utf-8")
        logger.info("Wrote Pandoc AST to %s", ast_dump_path)
    return json_str
