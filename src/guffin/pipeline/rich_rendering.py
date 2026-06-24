"""Rich terminal-rendering utilities for Roam node trees, vertex trees, and raw Datalog result tables.

Public symbols:

- :data:`DEFAULT_NODE_PANEL_PROPS` — the node property names rendered in a panel body by default.
- :data:`DEFAULT_VERTEX_PANEL_PROPS` — the vertex property names rendered in a panel body by default.
- :func:`build_node_panel` — render a :class:`~guffin.roam.node.RoamNode` as a Rich
  :class:`~rich.panel.Panel`.
- :func:`build_rich_node_tree` — build a Rich :class:`~rich.tree.Tree` from a
  :class:`~guffin.roam.node_tree.NodeTree` using a depth-first traversal.
- :func:`build_rich_refs_box` — build a Rich :class:`~rich.panel.Panel` summarising the
  back-reference nodes in a :class:`~guffin.roam.node_tree.NodeTree`.
- :func:`build_vertex_panel` — render a :data:`~guffin.vertex.Vertex` as a Rich
  :class:`~rich.panel.Panel`.
- :func:`build_rich_vertex_tree` — build a Rich :class:`~rich.tree.Tree` from a
  :class:`~guffin.vertex_tree.VertexTree` using a depth-first traversal.
- :func:`build_rich_raw_table` — build a Rich :class:`~rich.table.Table` of raw
  Datalog pull-blocks from a :class:`~guffin.roam.node_fetch_result.NodeFetchResult`.
"""

import logging
from typing import Final, TypeGuard, assert_never

import regex
from pydantic import validate_call

from rich.console import Group
from rich.markup import escape as markup_escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree as RichTree

from guffin.common.geometry import ImageSize
from guffin.common.table import Table as GuffinTable, TableStyle
from guffin.model.vertex import (
    BlockQuoteVertex,
    CalloutVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
    VertexType,
)
from guffin.model.vertex_tree import VertexTree, VertexTreeDFSIterator
from guffin.roam.node import NodeType, RoamNode, effective_heading_level, node_type
from guffin.roam.node_fetch_result import NodeFetchResult
from guffin.roam.node_tree import NodeTree, NodeTreeDFSIterator
from guffin.roam.markdown import IMAGE_LINK_RE, RoamCallout, parse_callout, strip_block_quote_marker
from guffin.roam.primitives import Id, IdObject, Uid

logger = logging.getLogger(__name__)

DEFAULT_NODE_PANEL_PROPS: Final[list[str]] = ["heading", "order", "children", "parents", "page"]
"""Property names rendered in the panel body by :func:`build_node_panel` when no explicit list is given.

``string``/``title`` and ``id`` are always shown in the panel title and are not
included here.  All other :class:`~guffin.roam.node.RoamNode` field names are
valid entries.
"""

DEFAULT_VERTEX_PANEL_PROPS: Final[list[str]] = ["vertex_type.value", "children", "refs"]
"""Property names rendered in the panel body by :func:`build_vertex_panel` when no explicit list is given.

Entries may use dotted-path notation (e.g. ``"vertex_type.value"``) to reach
nested attributes on the :data:`~guffin.vertex.Vertex`.
"""


def _format_node_prop(node: RoamNode, prop: str) -> str:
    """Return a ``name=value`` string for *prop* on *node*, for use in a panel body.

    Args:
        node: The node whose property is to be formatted.
        prop: A :class:`~guffin.roam.node.RoamNode` field name.

    Returns:
        A ``"name=value"`` string.  Unknown *prop* names produce ``"name=?"``.
    """
    match prop:
        case "order":
            return f"order={node.order}"
        case "children":
            val = f"[{', '.join(str(c.id) for c in node.children)}]" if node.children else "None"
            return f"children={val}"
        case "parents":
            val = f"[{', '.join(str(p.id) for p in node.parents)}]" if node.parents else "None"
            return f"parents={val}"
        case "page":
            val = str(node.page.id) if node.page is not None else "None"
            return f"page={val}"
        case "time":
            return f"time={node.time}"
        case "user":
            return f"user={node.user.id}"
        case "refs":
            val = f"[{', '.join(str(r.id) for r in node.refs)}]" if node.refs else "None"
            return f"refs={val}"
        case "open":
            return f"open={node.open}"
        case "sidebar":
            return f"sidebar={node.sidebar}"
        case "heading":
            return f"heading={node.heading}"
        case "attrs":
            return f"attrs={node.attrs}"
        case "props":
            return f"props={node.props}"
        case "lookup":
            val = f"[{', '.join(str(lk.id) for lk in node.lookup)}]" if node.lookup else "None"
            return f"lookup={val}"
        case "seen_by":
            val = f"[{', '.join(str(s.id) for s in node.seen_by)}]" if node.seen_by else "None"
            return f"seen_by={val}"
        case "uid":
            return f"uid={node.uid}"
        case "id":
            return f"id={node.id}"
        case "string":
            return f"string={node.string}"
        case "title":
            return f"title={node.title}"
        case _:
            return f"{prop}=?"


def _trunc(val: str, max_len: int = 40) -> str:
    return val[:max_len] + "…" if len(val) > max_len else val


@validate_call
def build_node_panel(node: RoamNode, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> Panel:
    """Render *node* as a Rich Panel for display in a terminal tree.

    The panel title has the form ``<node_type> title_text (id)`` where
    ``node_type`` is the :attr:`~guffin.roam.node.NodeType` value string.
    ``title_text`` is determined by :func:`~guffin.roam.node.node_type`:

    - :attr:`~guffin.roam.node.NodeType.ROAM_IMAGE_BLOCK` — ``[<alt>](<firestore_url>)``.
    - :attr:`~guffin.roam.node.NodeType.ROAM_HEADING_BLOCK` — when ``"heading"``
      is in *props*, ``H{n}: <string>`` (level from
      :func:`~guffin.roam.node.effective_heading_level`); otherwise the raw
      block string.
    - All other node types — the raw block string or page title.

    The panel body shows the remaining properties named in *props* as a single
    formatted line of ``name=value`` pairs; ``heading`` is excluded from the body
    because it is represented by the title prefix.

    Args:
        node: The node to render.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include.  Controls the ``H{n}:`` title prefix (shown only when
            ``"heading"`` is present) and the body pairs (``heading`` itself is
            never written to the body).  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.panel.Panel` with a labelled title and metadata body.
    """
    logger.debug("node=%r, props=%r", node, props)
    nt: Final[NodeType] = node_type(node)
    title_text: str
    match nt:
        case NodeType.ROAM_IMAGE_BLOCK:
            assert node.string is not None
            m = IMAGE_LINK_RE.search(node.string)
            assert m is not None
            title_text = f"[{m.group('alt')}](<firestore_url>)"
        case NodeType.ROAM_HEADING_BLOCK:
            level: Final[int | None] = effective_heading_level(node)
            title_text = f"H{level}: {node.string}"
        case NodeType.ROAM_PAGE:
            assert node.title is not None
            title_text = node.title
        case NodeType.ROAM_CALLOUT_BLOCK:
            assert node.string is not None
            callout: Final[RoamCallout | None] = parse_callout(node.string)
            assert callout is not None
            title_text = _trunc(callout.title)
        case NodeType.ROAM_PLAIN_BLOCK:
            assert node.string is not None
            title_text = _trunc(node.string)
        case NodeType.ROAM_CODE_BLOCK:
            assert node.string is not None
            title_text = _trunc(node.string)
        case NodeType.ROAM_BLOCK_QUOTE:
            assert node.string is not None
            title_text = _trunc(strip_block_quote_marker(node.string))
        case NodeType.ROAM_NATIVE_TABLE:
            assert node.string is not None
            title_text = _trunc(node.string)
        case NodeType.ROAM_EMBED_BLOCK:
            assert node.string is not None
            title_text = _trunc(node.string)
        case _ as unreachable:
            assert_never(unreachable)
    title: Final[str] = f"[#00aa00]<{nt.value}> [bold reverse]{title_text}[/bold reverse] ({node.id})[/#00aa00]"
    content: Final[str] = "  ".join(_format_node_prop(node, p) for p in props)
    return Panel(Text(content), title=title, expand=False)


@validate_call
def build_rich_node_tree(tree: NodeTree, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> RichTree:
    """Build a Rich tree from *tree* using a depth-first traversal.

    Iterates *tree* in pre-order depth-first order via
    :meth:`~guffin.roam.node_tree.NodeTree.dfs`, attaching each node as a Rich
    panel under its parent in the rendered tree.

    Args:
        tree: The :class:`~guffin.roam.node_tree.NodeTree` to render.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include in each panel body.  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.tree.Tree` rooted at the single root node of *tree*.
    """
    logger.debug("tree=%r, props=%r", tree, props)
    child_to_parent: Final[dict[Id, Id]] = {c.id: n.id for n in tree.tree_network if n.children for c in n.children}
    rich_node_map: Final[dict[Id, RichTree]] = {}
    dfs_iter: Final[NodeTreeDFSIterator] = tree.dfs()
    root_node: Final[RoamNode] = next(dfs_iter)
    root_rich: Final[RichTree] = RichTree(build_node_panel(root_node, props))
    rich_node_map[root_node.id] = root_rich
    for node in dfs_iter:
        parent_rich: RichTree = rich_node_map[child_to_parent[node.id]]
        rich_node_map[node.id] = parent_rich.add(build_node_panel(node, props))
    return root_rich


@validate_call
def build_rich_refs_box(tree: NodeTree, props: list[str] = DEFAULT_NODE_PANEL_PROPS) -> Panel | None:
    """Build a Rich :class:`~rich.panel.Panel` summarising the back-reference nodes in *tree*.

    For each node in :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id`, renders a
    two-column grid row containing a :func:`build_node_panel` on the left and a
    *referenced by* panel listing the ids of tree nodes that cite it on the right.
    All rows are collected into a single ``refs`` panel.

    Returns ``None`` when :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` is empty.

    Args:
        tree: The :class:`~guffin.roam.node_tree.NodeTree` whose
            :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` and
            :attr:`~guffin.roam.node_tree.NodeTree.tree_network` are used.
        props: Ordered list of :class:`~guffin.roam.node.RoamNode` field names
            to include in each node panel body.  Defaults to :data:`DEFAULT_NODE_PANEL_PROPS`.

    Returns:
        A :class:`~rich.panel.Panel` titled ``refs`` grouping one row per referenced
        node, or ``None`` when *tree* has no refs.
    """
    if not tree.refs_by_id:
        return None
    referencing_ids_by_ref_id: Final[dict[Id, list[Id]]] = {
        ref_id: [n.id for n in tree.tree_network if n.refs is not None and any(r.id == ref_id for r in n.refs)]
        for ref_id in tree.refs_by_id
    }
    ref_rows: Final[list[Table]] = []
    for ref_node in tree.refs_by_id.values():
        back_ref_text: str = "  ".join(str(i) for i in referencing_ids_by_ref_id[ref_node.id])
        back_refs_panel: Panel = Panel(back_ref_text or "(none)", title="referenced by")
        row: Table = Table.grid(padding=(0, 1))
        row.add_column()
        row.add_column()
        row.add_row(build_node_panel(ref_node, props), back_refs_panel)
        ref_rows.append(row)
    return Panel(Group(*ref_rows), title="refs")


def _format_vertex_table_style_prop(vertex: TableVertex) -> Text:
    """Format *vertex*'s :class:`~guffin.common.table.TableStyle` as a ``name=value`` :class:`~rich.text.Text`.

    Args:
        vertex: The table vertex whose :attr:`~guffin.vertex.TableVertex.table_style` is rendered.

    Returns:
        A :class:`~rich.text.Text` summarising the key style fields.
    """
    sty: Final[TableStyle] = vertex.table_style
    return Text(
        f"table_style=(row_hdr={sty.header_row_style}, col_hdr={sty.header_col_style}, "
        f"default={sty.default_cell_style}, n_overrides={len(sty.cell_styles)}, "
        f"widths={sty.column_widths})"
    )


def _format_vertex_table_prop(vertex: TableVertex) -> Table:
    """Build a Rich :class:`~rich.table.Table` from *vertex*'s embedded table data.

    Args:
        vertex: The table vertex whose :attr:`~guffin.vertex.TableVertex.table` is rendered.

    Returns:
        A :class:`~rich.table.Table` populated with the cell grid.
    """
    guffin_tbl: Final[GuffinTable] = vertex.table
    rich_tbl: Final[Table] = Table(show_lines=True, show_header=guffin_tbl.has_row_header)
    data_start: Final[int] = 1 if guffin_tbl.has_row_header else 0
    if guffin_tbl.has_row_header:
        for header_cell in guffin_tbl.rows[0]:
            rich_tbl.add_column(header_cell, style="bold")
    else:
        for col_idx in range(guffin_tbl.num_cols):
            rich_tbl.add_column(f"col {col_idx + 1}")
    for row in guffin_tbl.rows[data_start:]:
        rich_tbl.add_row(*row)
    return rich_tbl


def _format_vertex_prop(vertex: Vertex, prop: str) -> Text | Table:
    """Return a styled ``name=value`` :class:`~rich.text.Text` for *prop* on *vertex*.

    Args:
        vertex: The vertex whose property is to be formatted.
        prop: A :data:`~guffin.vertex.Vertex` field name, or a dotted-path expression
            such as ``"vertex_type.value"``.

    Returns:
        A :class:`~rich.text.Text` rendering ``name=value``.  Unknown *prop* names
        produce ``"name=?"``.  For vertex-type props the value portion is bold orange.
    """
    match prop:
        case "vertex_type.value":
            return Text.assemble("type=", (vertex.vertex_type.value.split("/", 1)[-1], "bold orange1"))
        case "vertex_type":
            return Text.assemble("vertex_type=", (vertex.vertex_type.value.split("/", 1)[-1], "bold orange1"))
        case "uid":
            return Text(f"uid={vertex.uid}")
        case "title":
            return Text(f"title={vertex.title}" if isinstance(vertex, PageVertex) else "title=N/A")
        case "text":
            return Text(f"text={vertex.text}" if isinstance(vertex, TextVertex | BlockQuoteVertex) else "text=N/A")
        case "file_name":
            return Text(f"file_name={vertex.file_name}" if isinstance(vertex, ImageVertex) else "file_name=N/A")
        case "media_type":
            return Text(
                f"media_type={vertex.media_type.value}" if isinstance(vertex, ImageVertex) else "media_type=N/A"
            )
        case "scaled_image_size":
            return Text(
                f"scaled_image_size=({vertex.scaled_image_size})"
                if isinstance(vertex, ImageVertex)
                else "scaled_image_size=N/A"
            )
        case "original_image_size":
            if not isinstance(vertex, ImageVertex):
                return Text("original_image_size=N/A")
            size: Final[ImageSize | None] = vertex.original_image_size
            return Text(f"original_image_size=({size})" if size is not None else "original_image_size=None")
        case "source":
            return Text(f"source={vertex.source}" if isinstance(vertex, ImageVertex) else "source=N/A")
        case "alt_text":
            return Text(f"alt_text={vertex.alt_text}" if isinstance(vertex, ImageVertex) else "alt_text=N/A")
        case "body":
            return Text(f"body={vertex.body}" if isinstance(vertex, CalloutVertex) else "body=N/A")
        case "children":
            val: str = f"[{', '.join(vertex.children)}]" if vertex.children else "None"
            return Text(f"children={val}")
        case "refs":
            val = f"[{', '.join(vertex.refs)}]" if vertex.refs else "None"
            return Text(f"refs={val}")
        case "table":
            if not isinstance(vertex, TableVertex):
                return Text("table=N/A")
            return _format_vertex_table_prop(vertex)
        case "table_style":
            if not isinstance(vertex, TableVertex):
                return Text("table_style=N/A")
            return _format_vertex_table_style_prop(vertex)
        case _:
            return Text(f"{prop}=?")


@validate_call
def build_vertex_panel(vertex: Vertex, props: list[str] = DEFAULT_VERTEX_PANEL_PROPS) -> Panel:
    """Render *vertex* as a Rich Panel for display in a terminal tree.

    The panel title shows a type-specific summary with the vertex ``uid`` in
    parentheses:

    - :class:`~guffin.vertex.PageVertex` — page title.
    - :class:`~guffin.vertex.HeadingVertex` — ``H{n}: <text>``.
    - :class:`~guffin.vertex.TextVertex` — block text as-is.
    - :class:`~guffin.vertex.ImageVertex` — ``IMAGE [<alt>](<firestore_url>)``.
    - :class:`~guffin.vertex.CalloutVertex` — ``CALLOUT [<type>]: <title>``.

    The panel body renders each name in *props* via :func:`_format_vertex_prop`.

    Args:
        vertex: The :data:`~guffin.vertex.Vertex` to render.
        props: Vertex property names to include in the panel body.  Defaults to
            :data:`DEFAULT_VERTEX_PANEL_PROPS`.

    Returns:
        A :class:`~rich.panel.Panel` with a labelled title and metadata body.
    """
    logger.debug("vertex=%r", vertex)
    title_content: str
    match vertex.vertex_type:
        case VertexType.GUFFIN_PAGE:
            title_content = f"[bold #00aa00]{markup_escape(vertex.title)}[/bold #00aa00]"
        case VertexType.GUFFIN_HEADING:
            title_content = (
                f"[bold orange1]H{vertex.heading_level}[/bold orange1]"
                f"[bold #00aa00]{markup_escape(f': {_trunc(vertex.text)}')}[/bold #00aa00]"
            )
        case VertexType.GUFFIN_TEXT:
            title_content = f"[bold #00aa00]{markup_escape(_trunc(vertex.text))}[/bold #00aa00]"
        case VertexType.GUFFIN_IMAGE:
            title_content = (
                f"[bold orange1]{markup_escape(f'IMAGE [{vertex.alt_text or ""}]')}[/bold orange1]"
                f"[bold #00aa00](<firestore_url>)[/bold #00aa00]"
            )
        case VertexType.GUFFIN_CALLOUT:
            title_content = (
                f"[bold orange1]{markup_escape(f'CALLOUT [{vertex.callout_type.value}]:')}[/bold orange1]"
                f" [bold #00aa00]{markup_escape(_trunc(vertex.title))}[/bold #00aa00]"
            )
        case VertexType.GUFFIN_CODE_BLOCK:
            title_content = (
                f"[bold orange1]{markup_escape(f'CODE [{vertex.language.value}]:')}[/bold orange1]"
                f" [bold #00aa00]{markup_escape(_trunc(vertex.code))}[/bold #00aa00]"
            )
        case VertexType.GUFFIN_BLOCK_QUOTE:
            title_content = (
                f"[bold orange1]{markup_escape('QUOTE:')}[/bold orange1]"
                f" [bold #00aa00]{markup_escape(_trunc(vertex.text))}[/bold #00aa00]"
            )
        case VertexType.GUFFIN_TABLE:
            title_content = (
                f"[bold orange1]{markup_escape('TABLE')}[/bold orange1]"
                f" [bold #00aa00]{markup_escape(f'({vertex.table.num_rows}×{vertex.table.num_cols})')}[/bold #00aa00]"
            )
        case VertexType.GUFFIN_BLOCK_EMBED:
            title_content = (
                f"[bold orange1]{markup_escape('EMBED:')}[/bold orange1]"
                f" [bold #00aa00]{markup_escape(vertex.vertex_link.uid)}[/bold #00aa00]"
            )
        case _ as unreachable:
            assert_never(unreachable)
    title: Final[str] = f"{title_content} [dim]({vertex.uid})[/dim]"
    effective_props: Final[list[str]] = (
        [*props, "table"] if isinstance(vertex, TableVertex) and "table" not in props else props
    )
    prop_renderings: Final[list[Text | Table]] = [_format_vertex_prop(vertex, p) for p in effective_props]
    text_props: Final[list[Text]] = [ren for ren in prop_renderings if isinstance(ren, Text)]
    table_props: Final[list[Table]] = [ren for ren in prop_renderings if isinstance(ren, Table)]
    meta_line: Final[Text] = Text("  ").join(text_props) if text_props else Text("")
    content: Final[Text | Group] = Group(meta_line, *table_props) if table_props else meta_line
    return Panel(content, title=title, expand=False)


@validate_call
def build_rich_vertex_tree(vertex_tree: VertexTree, props: list[str] = DEFAULT_VERTEX_PANEL_PROPS) -> RichTree:
    """Build a Rich tree from *vertex_tree* using a depth-first traversal.

    Locates the root vertex (the one not referenced as a child by any other
    vertex), then performs an iterative pre-order DFS, attaching each vertex
    as a Rich panel under its parent in the rendered tree.

    Args:
        vertex_tree: The :class:`~guffin.vertex_tree.VertexTree` to render.
        props: Vertex property names to include in each panel body.  Defaults to
            :data:`DEFAULT_VERTEX_PANEL_PROPS`.

    Returns:
        A :class:`~rich.tree.Tree` rooted at the single root vertex of
        *vertex_tree*.
    """
    logger.debug("vertex_tree=%r", vertex_tree)
    child_to_parent: Final[dict[Uid, Uid]] = {
        child_uid: v.uid for v in vertex_tree.tree_vertices if v.children for child_uid in v.children
    }
    rich_map: Final[dict[Uid, RichTree]] = {}
    dfs_iter: Final[VertexTreeDFSIterator] = vertex_tree.dfs()
    root: Final[Vertex] = next(dfs_iter)
    root_rich: Final[RichTree] = RichTree(build_vertex_panel(root, props))
    rich_map[root.uid] = root_rich
    for vertex in dfs_iter:
        parent_rich: RichTree = rich_map[child_to_parent[vertex.uid]]
        rich_map[vertex.uid] = parent_rich.add(build_vertex_panel(vertex, props))
    return root_rich


# ---------------------------------------------------------------------------
# Raw-results table
# ---------------------------------------------------------------------------


def _is_id_ref_dict(val: object) -> TypeGuard[dict[str, object]]:
    """Return True iff *val* is a single-entry ``{"id": <value>}`` dict."""
    if not isinstance(val, dict):
        return False
    return len(val) == 1 and "id" in val  # type: ignore[arg-type]


def _is_obj_list(val: object) -> TypeGuard[list[object]]:
    """Return True iff *val* is a list."""
    return isinstance(val, list)


_RAW_RESULTS_EXCLUDED_ATTRS: Final[frozenset[str]] = frozenset(
    {
        "open",
        "prevent-clean",
        "sidebar",
        "time",
        "user",
        "edit-nonce",
        "edit-time",
        "edit-user",
        "word-count",
    }
)
"""Pull-block attribute keys suppressed from the raw-results Rich table."""

_RAW_RESULTS_COL_ORDER: Final[tuple[str, ...]] = (
    "id",
    "uid",
    "string",
    "title",
    "children",
    "order",
    "parents",
    "page",
    "heading",
    "props",
)
"""Preferred left-to-right column order for the raw-results Rich table.

Columns whose key appears in this tuple are placed first, in the order listed.
All remaining (unrecognized) columns follow, sorted alphabetically.
"""

_RAW_RESULTS_COL_HEADERS: Final[dict[str, str]] = {
    "heading": "H",
    "order": "ord",
}
"""Override display headers for the raw-results Rich table (key → header label).

Keys absent from this dict use the raw attribute name as the header.
"""

_RAW_RESULTS_COL_STYLES: Final[dict[str, str]] = {
    # identity
    "id": "bold yellow",
    "uid": "bold yellow",
    # text content
    "string": "bold green",
    "title": "bold green",
    # structure / relationships
    "children": "bold cyan",
    "order": "bold cyan",
    "parents": "bold cyan",
    "page": "bold cyan",
    "refs": "bold cyan",
    # display
    "heading": "bold magenta",
    # extended attributes
    "props": "bold blue",
}
"""Rich header styles for the raw-results table, keyed by raw attribute name.

Columns absent from this dict fall back to ``"bold white"``.
"""

_RAW_RESULTS_COL_STYLE_DEFAULT: Final[str] = "bold white"
"""Fallback Rich header style for columns not listed in :data:`_RAW_RESULTS_COL_STYLES`."""

_RAW_RESULTS_COL_TRUNCATE: Final[dict[str, int]] = {
    "string": 30,
}
"""Maximum display length (in characters) for specific columns in the raw-results table.

Cell values longer than the limit are silently truncated to that many characters.
"""

_URL_RE: Final[regex.Pattern[str]] = regex.compile(r"https?://[^\s\"']+")
"""Regex that matches ``http://`` or ``https://`` URLs, stopping before whitespace or quotes."""


def _truncate_urls_in_cell(cell: str) -> str:
    """Replace each URL in *cell* with its first 15 characters followed by ``…``.

    URLs are detected by :data:`_URL_RE`.  Matches shorter than 15 characters
    are left unchanged.
    """

    def _shorten(match: regex.Match[str]) -> str:
        url: Final[str] = match.group()
        return url[:15] + "…" if len(url) > 15 else url

    return _URL_RE.sub(_shorten, cell)


@validate_call
def build_rich_raw_table(fetch_result: NodeFetchResult) -> Table:
    """Build and return a Rich :class:`~rich.table.Table` of raw Datalog pull-blocks.

    Rows are sorted by ``id``; columns cover every attribute key present across
    all pull-blocks, excluding those in :data:`_RAW_RESULTS_EXCLUDED_ATTRS`, and
    ordered according to :data:`_RAW_RESULTS_COL_ORDER` (remaining keys follow
    alphabetically).  :class:`~guffin.roam.primitives.IdObject` values and
    single-entry ``{"id": …}`` ref dicts are rendered as plain integer ids; lists
    of such refs are rendered as a comma-separated id sequence.  Column headers
    are overridden per :data:`_RAW_RESULTS_COL_HEADERS`; cell values are
    truncated per :data:`_RAW_RESULTS_COL_TRUNCATE`; URLs inside ``props``
    cells are additionally shortened to 15 characters via
    :func:`_truncate_urls_in_cell`.

    Args:
        fetch_result: Fetch result whose :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.raw_result`
            supplies the pull-block rows.

    Returns:
        A fully populated :class:`~rich.table.Table` ready for printing.
    """
    pull_blocks: Final[list[dict[str, object]]] = sorted(
        (row[0] for row in fetch_result.raw_result),
        key=lambda pb: v if isinstance(v := pb.get("id"), int) else 0,
    )
    col_rank: Final[dict[str, int]] = {k: i for i, k in enumerate(_RAW_RESULTS_COL_ORDER)}
    all_keys: Final[list[str]] = sorted(
        {key for pb in pull_blocks for key in pb} - _RAW_RESULTS_EXCLUDED_ATTRS,
        key=lambda k: (col_rank.get(k, len(_RAW_RESULTS_COL_ORDER)), k),
    )
    raw_table: Final[Table] = Table(show_lines=True)
    for key in all_keys:
        raw_table.add_column(
            _RAW_RESULTS_COL_HEADERS.get(key, key),
            header_style=_RAW_RESULTS_COL_STYLES.get(key, _RAW_RESULTS_COL_STYLE_DEFAULT),
            overflow="fold",
        )
    for pb in pull_blocks:
        row_vals: list[str] = []
        for key in all_keys:
            val: object = pb.get(key, "")
            cell: str
            if isinstance(val, IdObject):
                cell = str(val.id)
            elif _is_id_ref_dict(val):
                cell = str(val.get("id", ""))
            elif _is_obj_list(val):
                id_parts: list[str] = []
                is_id_list: bool = True
                for raw_el in val:
                    if isinstance(raw_el, IdObject):
                        id_parts.append(str(raw_el.id))
                    elif _is_id_ref_dict(raw_el):
                        id_parts.append(str(raw_el.get("id", "")))
                    else:
                        is_id_list = False
                        break
                cell = ", ".join(id_parts) if is_id_list else str(val)
            else:
                cell = str(val)
            if key == "props":
                cell = _truncate_urls_in_cell(cell)
            trunc: int | None = _RAW_RESULTS_COL_TRUNCATE.get(key)
            if trunc is not None:
                cell = cell[:trunc]
            row_vals.append(cell)
        raw_table.add_row(*row_vals)
    return raw_table
