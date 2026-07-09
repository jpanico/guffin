"""Normalize Roam flavored Markdown to Pandoc Markdown.

Roam Research uses a Markdown dialect ("Roamdown") that diverges from standard
Markdown in several ways.  This module transforms a single Roam block string into
a Pandoc Markdown-compatible string.  See ``docs/roam-md.md`` for a full
description of the differences.

The conversion functions operate on plain Python strings (one block string at a
time) and are stateless and side-effect-free.  They are designed to be composed
via :func:`to_pandoc_md`, which applies every transformation in a defined,
stable order.

Constructs intentionally left verbatim for future expansion:

- Block embeds — ``{{embed: ((block-uid))}}``
- Page embeds — ``{{embed: [[<page_name>]]}}``
- Other Roam components — ``{{TODO}}``, ``{{DONE}}``, ``{{query: ...}}``, etc.

Public symbols:

- :func:`to_pandoc_md` — apply all conversions to a Roam block string and
  return the Pandoc Markdown result.
- :func:`convert_color_bold` — convert Color Highlighter ``#c:COLOR **text**``
  spans → ``[**text**]{color="color"}`` bracketed spans.
- :func:`convert_color_highlight` — convert Color Highlighter ``#c:COLOR ^^text^^``
  spans → ``[text]{.mark highlight-color="color"}`` bracketed spans.
- :func:`convert_color_underline` — convert Color Highlighter ``#c:COLOR __text__``
  spans → ``[text]{underline-color="color"}`` bracketed spans.
- :func:`convert_color_box` — convert Color Highlighter ``#c:COLOR ~~text~~``
  spans → ``[text]{box-color="color"}`` bracketed spans.
- :func:`convert_bg_color_line` — convert Color Highlighter ``text #.bg-COLOR``
  whole-line background spans → ``[text]{bg-color="color"}`` bracketed spans.
- :func:`convert_code_blocks` — reposition Roam fenced code blocks so the
  opening and closing ```` ``` ```` fences each sit on their own line.
- :func:`convert_italics` — convert ``__italic__`` → ``*italic*``.
- :func:`convert_highlights` — convert ``^^text^^`` → ``[text]{.mark}``.
- :func:`convert_page_link_aliases` — convert ``[display]([[Page Name]])``
  → ``[display](Page Name)``.
- :func:`convert_page_link` — convert Roam page references ``[[Page Name]]`` to
  Pandoc Markdown vertex links ``[Page Name](x-guffin:vertex/<uid>)``, falling
  back to delimiter-stripped text when the page is not resolvable.
- :func:`convert_block_link` — convert Roam block references ``((uid))`` to
  Pandoc Markdown vertex links ``[display](x-guffin:vertex/<uid>)``, falling
  back to the verbatim ``((uid))`` when the block is not resolvable.
"""

from typing import Final

import regex
from pydantic import validate_call

from guffin.common.markdown import CODE_BLOCK_RE
from guffin.model.vertex_link import VertexLinkKind, vertex_link_url
from guffin.roam.markdown import (
    BG_COLOR_LINE_RE,
    BLOCK_REF_RE,
    COLOR_BOLD_RE,
    COLOR_BOX_RE,
    COLOR_HIGHLIGHT_RE,
    COLOR_UNDERLINE_RE,
    HIGHLIGHT_RE,
    ITALIC_RE,
    PAGE_LINK_ALIAS_RE,
    PAGE_REF_RE,
)
from guffin.roam.node import RoamNode
from guffin.roam.node_tree import NodeTree

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@validate_call
def to_pandoc_md(roam_string: str, tree: NodeTree) -> str:
    """Convert a Roam block string to Pandoc Markdown by applying all transformations.

    Transformations are applied in a fixed order designed to avoid
    double-substitution artefacts.  Each individual conversion is also
    available as a standalone function for testing or selective use.

    The following Roam constructs are intentionally left verbatim for future
    expansion: block embeds ``{{embed: ((uid))}}`` and other ``{{…}}`` components.

    Args:
        roam_string: A single Roam block string (the raw ``string`` field from a
            :class:`~guffin.roam.node.RoamNode`).
        tree: The :class:`~guffin.roam.node_tree.NodeTree` whose
            :attr:`~guffin.roam.node_tree.NodeTree.page_name_map` is used by
            :func:`convert_page_link` to resolve page-reference titles to UIDs.
            References to pages absent from the map fall back to plain text.

    Returns:
        The Pandoc Markdown string.
    """
    result: str = roam_string
    result = convert_color_bold(result)
    result = convert_color_highlight(result)
    result = convert_color_underline(result)
    result = convert_color_box(result)
    result = convert_code_blocks(result)
    result = convert_page_link_aliases(result)
    result = convert_page_link(result, tree)
    result = convert_block_link(result, tree)
    result = convert_italics(result)
    result = convert_highlights(result)
    result = convert_bg_color_line(result)
    return result


@validate_call
def convert_color_bold(roam_string: str) -> str:
    """Convert Color Highlighter colorized bold spans to Pandoc bracketed spans.

    The Color Highlighter Roam extension uses ``#c:COLOR **bold text**`` to
    render bold text in a named color.  Each such span is converted to a Pandoc
    bracketed span with a ``color`` attribute:
    ``[**bold text**]{color="orange"}``.  The color name is lowercased for
    CSS compatibility.  Must run before other conversions so that any Roam
    constructs inside the bold content are still available for subsequent steps.

    Args:
        roam_string: A Roam block string, possibly containing
            ``#c:COLOR **text**`` spans.

    Returns:
        The string with all ``#c:COLOR **text**`` spans replaced by
        ``[**text**]{color="color"}`` bracketed spans.
    """
    return COLOR_BOLD_RE.sub(
        lambda match: f'[**{match.group(2)}**]{{color="{match.group(1).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_color_highlight(roam_string: str) -> str:
    """Convert Color Highlighter colorized highlight spans to Pandoc bracketed spans.

    The Color Highlighter Roam extension uses ``#c:COLOR ^^text^^`` to render
    text with a named background-color highlight.  Each such span is converted
    to a Pandoc bracketed span with class ``mark`` and a ``highlight-color``
    attribute: ``[text]{.mark highlight-color="orange"}``.  The color name is
    lowercased for CSS compatibility.  The ``mark`` class preserves compatibility
    with the default highlight pipeline; ``highlight-color`` signals that a
    specific color was requested.  Must run before :func:`convert_highlights` so
    that the ``^^...^^`` delimiters are still present.

    Args:
        roam_string: A Roam block string, possibly containing
            ``#c:COLOR ^^text^^`` spans.

    Returns:
        The string with all ``#c:COLOR ^^text^^`` spans replaced by
        ``[text]{.mark highlight-color="color"}`` bracketed spans.
    """
    return COLOR_HIGHLIGHT_RE.sub(
        lambda match: f'[{match.group(2)}]{{.mark highlight-color="{match.group(1).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_color_underline(roam_string: str) -> str:
    """Convert Color Highlighter colorized underline spans to Pandoc bracketed spans.

    The Color Highlighter Roam extension uses ``#c:COLOR __text__`` to render
    text with a colored underline.  Each such span is converted to a Pandoc
    bracketed span with an ``underline-color`` attribute:
    ``[text]{underline-color="orange"}``.  The color name is lowercased for
    CSS compatibility.  No ``underline`` class is added, to prevent Pandoc from
    treating the span as a native ``Underline`` element and silently dropping
    the color attribute.  Must run before :func:`convert_italics` because Roam
    also uses ``__text__`` for italics.

    Args:
        roam_string: A Roam block string, possibly containing
            ``#c:COLOR __text__`` spans.

    Returns:
        The string with all ``#c:COLOR __text__`` spans replaced by
        ``[text]{underline-color="color"}`` bracketed spans.
    """
    return COLOR_UNDERLINE_RE.sub(
        lambda match: f'[{match.group(2)}]{{underline-color="{match.group(1).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_color_box(roam_string: str) -> str:
    """Convert Color Highlighter colorized box spans to Pandoc bracketed spans.

    The Color Highlighter Roam extension uses ``#c:COLOR ~~text~~`` to render
    text surrounded by a colored box.  Each such span is converted to a Pandoc
    bracketed span with a ``box-color`` attribute:
    ``[text]{box-color="orange"}``.  The color name is lowercased for
    CSS compatibility.  Must run before Pandoc processes the string because
    Pandoc treats ``~~text~~`` as strikethrough.

    Args:
        roam_string: A Roam block string, possibly containing
            ``#c:COLOR ~~text~~`` spans.

    Returns:
        The string with all ``#c:COLOR ~~text~~`` spans replaced by
        ``[text]{box-color="color"}`` bracketed spans.
    """
    return COLOR_BOX_RE.sub(
        lambda match: f'[{match.group(2)}]{{box-color="{match.group(1).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_bg_color_line(roam_string: str) -> str:
    """Convert a Color Highlighter whole-line background span to a Pandoc bracketed span.

    The Color Highlighter Roam extension appends ``#.bg-COLOR`` to a block
    string to apply a background color to the entire line.  This function
    strips the suffix and wraps the entire remaining content in a Pandoc
    bracketed span with a ``bg-color`` attribute:
    ``[text]{bg-color="orange"}``.  The color name is lowercased for CSS
    compatibility.  Must run last in the pipeline so that any inline color
    spans within the block text are already converted before the outer wrapper
    is applied.

    Args:
        roam_string: A Roam block string, possibly ending with
            ``#.bg-COLOR``.

    Returns:
        The string with the ``#.bg-COLOR`` suffix stripped and the content
        wrapped in ``[...]{bg-color="color"}``, or *roam_string* unchanged
        if the suffix is absent.
    """
    return BG_COLOR_LINE_RE.sub(
        lambda match: f'[{match.group(1)}]{{bg-color="{match.group(2).lower()}"}}',
        roam_string,
    )


@validate_call
def convert_code_blocks(roam_string: str) -> str:
    r"""Reposition Roam fenced code blocks so each fence sits on its own line.

    Roam stores a fenced code block as ```` ```lang\ncode``` ````, where the
    opening fence (with its language tag) can share a line with preceding text
    and the closing fence trails the final code line.  Pandoc only recognises a
    fenced code block when both the opening and closing ```` ``` ```` fences
    begin their own lines, so this function inserts the newlines needed to
    isolate them:

    - a newline is inserted before the opening fence unless it already starts
      the string or follows a newline;
    - the closing fence is moved onto its own line directly after the code body;
    - a newline is inserted after the closing fence when trailing content
      follows it on the same line.

    The language/info string on the opening fence is preserved verbatim.

    Args:
        roam_string: A Roam block string, possibly containing fenced code blocks.

    Returns:
        The string with every fenced code block repositioned onto isolated
        fence lines.
    """

    def _reposition(match: regex.Match[str]) -> str:
        language: str = match.group(1)
        body: str = match.group(2).rstrip("\n")
        prefix: str = "" if match.start() == 0 or match.string[match.start() - 1] == "\n" else "\n"
        suffix: str = "" if match.end() == len(match.string) or match.string[match.end()] == "\n" else "\n"
        return f"{prefix}```{language}\n{body}\n```{suffix}"

    return CODE_BLOCK_RE.sub(_reposition, roam_string)


@validate_call
def convert_italics(roam_string: str) -> str:
    """Convert Roam italic syntax to Pandoc Markdown italic syntax.

    Roam uses ``__double underscores__`` for italics; Pandoc Markdown uses
    ``*single asterisks*``.  This function replaces every ``__text__`` span
    with ``*text*``.

    Args:
        roam_string: A Roam block string, possibly containing ``__italic__`` spans.

    Returns:
        The string with all ``__italic__`` spans replaced by ``*italic*``.
    """
    return ITALIC_RE.sub(r"*\1*", roam_string)


@validate_call
def convert_highlights(roam_string: str) -> str:
    """Convert Roam highlight syntax to a Pandoc Markdown bracketed span.

    Roam uses ``^^text^^`` for background highlights.  Pandoc Markdown
    represents this as ``[text]{.mark}`` via the ``bracketed_spans`` extension
    (enabled by default in Pandoc Markdown), which maps to a ``Span`` AST node
    with class ``mark``.

    Args:
        roam_string: A Roam block string, possibly containing ``^^highlight^^`` spans.

    Returns:
        The string with all ``^^text^^`` spans replaced by ``[text]{.mark}``.
    """
    return HIGHLIGHT_RE.sub(r"[\1]{.mark}", roam_string)


@validate_call
def convert_page_link_aliases(roam_string: str) -> str:
    """Convert Roam page-link aliases to Pandoc Markdown inline links.

    Roam supports ``[display text]([[Page Name]])`` to create an aliased link
    to a page.  This function converts each such construct to the Pandoc
    Markdown inline link ``[display text](Page Name)``, removing the
    ``[[``/``]]`` delimiters and using the page name as the link destination.

    Must be applied before :func:`convert_page_link` so that the ``[[…]]``
    target is identified and converted rather than blindly stripped.

    Args:
        roam_string: A Roam block string, possibly containing alias patterns.

    Returns:
        The string with all ``[display]([[Page Name]])`` patterns replaced by
        ``[display](Page Name)``.
    """
    return PAGE_LINK_ALIAS_RE.sub(r"[\1](\2)", roam_string)


@validate_call
def convert_page_link(roam_string: str, tree: NodeTree) -> str:
    """Convert Roam page references to Pandoc Markdown links to the referenced vertex.

    Each balanced Roam page reference ``[[Page Name]]`` (as matched by
    :data:`~guffin.roam.markdown.PAGE_REF_RE`, including nested references) is
    converted to a Pandoc Markdown inline link whose destination is an
    ``x-guffin`` vertex-reference URL (see
    :func:`~guffin.link.vertex_link_url`): ``[Page Name](x-guffin:vertex/<uid>)``.
    The destination UID is resolved by looking up the page title in *tree*'s
    :attr:`~guffin.roam.node_tree.NodeTree.page_name_map`.

    When the title is not found in
    :attr:`~guffin.roam.node_tree.NodeTree.page_name_map` (e.g. the referenced page
    was not fetched), the reference falls back to its plain inner text with the
    ``[[`` and ``]]`` delimiters stripped — so ``[[Page Name]]`` becomes
    ``Page Name`` and ``[[nested [[pages]]]]`` becomes ``nested pages``.  The
    link text is likewise the delimiter-stripped page name.

    Args:
        roam_string: A Roam block string, possibly containing ``[[…]]`` references.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` whose
            :attr:`~guffin.roam.node_tree.NodeTree.page_name_map` supplies the
            title-to-UID resolution.

    Returns:
        The string with every resolvable page reference replaced by a Pandoc
        Markdown vertex link, and every unresolvable reference replaced by its
        delimiter-stripped text.
    """

    def _replace(match: regex.Match[str]) -> str:
        page_name: Final[str] = match.group("page_name")
        display: Final[str] = page_name.replace("[[", "").replace("]]", "")
        if page_name not in tree.page_name_map:
            return display
        return f"[{display}]({vertex_link_url(tree.page_name_map[page_name].uid, VertexLinkKind.REFERENCE)})"

    return PAGE_REF_RE.sub(_replace, roam_string)


@validate_call
def convert_block_link(roam_string: str, tree: NodeTree) -> str:
    """Convert Roam block references to Pandoc Markdown links to the referenced vertex.

    Each Roam block reference ``((uid))`` (as matched by
    :data:`~guffin.roam.markdown.BLOCK_REF_RE`) is converted to a Pandoc Markdown
    inline link whose destination is an ``x-guffin`` vertex-reference URL (see
    :func:`~guffin.link.vertex_link_url`): ``[display](x-guffin:vertex/<uid>)``.
    The display text is the referenced node's ``string`` content (for block nodes)
    or its ``title`` (for page nodes), falling back to the bare UID if both are
    absent.

    When the UID is absent from *tree* (e.g. the referenced block was not
    fetched), the reference is left verbatim as ``((uid))``.

    Args:
        roam_string: A Roam block string, possibly containing ``((uid))`` block references.
        tree: The :class:`~guffin.roam.node_tree.NodeTree` used to resolve block UIDs
            to :class:`~guffin.roam.node.RoamNode` instances.  Both
            :attr:`~guffin.roam.node_tree.NodeTree.tree_network` nodes and
            :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` nodes are searched.

    Returns:
        The string with every resolvable block reference replaced by a Pandoc
        Markdown vertex link, and every unresolvable reference left verbatim as
        ``((uid))``.
    """

    def _replace(match: regex.Match[str]) -> str:
        uid: Final[str] = match.group("uid")
        if uid not in tree.uid_map:
            return match.group(0)
        node: Final[RoamNode] = tree.uid_map[uid]
        display: Final[str] = node.string or node.title or uid
        return f"[{display}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"

    return BLOCK_REF_RE.sub(_replace, roam_string)
