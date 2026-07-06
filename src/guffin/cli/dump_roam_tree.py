#!/usr/bin/env python3
"""CLI tool for dumping a Roam Research page or node subtree as a Rich tree to the terminal.

Fetches Roam nodes identified by ``TARGET`` via the Roam Local API and renders
one or more of the following as a colorized :class:`~rich.tree.Tree` panel
hierarchy:

- **Vertex tree** (default, ``--vertex-tree`` / ``-v/-V``) — normalized
  :class:`~guffin.vertex_tree.VertexTree` produced by
  :func:`~guffin.transcribe.roam_tree_to_guffin.transcribe`; image vertices are
  enriched with their native pixel size (fetched via the Local API) before display.
- **Node tree** (``--node-tree`` / ``-n/-N``) — raw :class:`~guffin.roam.node_tree.NodeTree`
  as returned by the Roam Local API; each panel body lists selected
  :class:`~guffin.roam.node.RoamNode` fields, configurable via
  ``--node-props`` (defaults to
  :data:`~guffin.render.rich_rendering.DEFAULT_NODE_PANEL_PROPS`).
- **Raw results** (``--raw-results`` / ``-r/-R``) — raw Datalog query results
  as returned by the Roam Local API, before any transcription.

``TARGET`` accepts a Roam **page title** (optionally wrapped in ``[[ ]]``), a
**node UID**, or a Roam **block reference** ``((uid))``.  It is treated as a node
UID when wrapped in ``(( ))`` or when it matches
:data:`~guffin.roam.primitives.ANCHORED_UID_PATTERN` — either a synthetic
nine-character UID or an ``MM-DD-YYYY`` Daily Note Page UID; otherwise it is
treated as a page title (any ``[[ ]]`` wrapper is stripped).  A page whose title
happens to match one of those UID forms would be misidentified — this edge case
is considered negligible in practice.

Logging is colorized by level via :mod:`guffin.logging_config` and
configurable via the ``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :func:`dump_trees` — dispatches to the enabled display functions based on
  the ``show_*`` flags.
- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``dump-roam-tree``
  console script.

Example::

    dump-roam-tree "Test Article" -p 3333 -g SCFH -t your-bearer-token
    dump-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t tok
    dump-roam-tree "Test Article" -p 3333 -g SCFH -t tok -n --node-props heading,parents
    dump-roam-tree "Test Article" -p 3333 -g SCFH -t tok -i -r -n -v
"""

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Final

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree as RichTree

from guffin.cli.common import fetch_roam_trees
from guffin.cli.logging_config import configure_logging
from guffin.cli.params import GraphOption, PortOption, TargetArgument, TokenOption
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree
from guffin.render.asset_fetch import fetch_and_enrich_assets
from guffin.render.rich_rendering import (
    DEFAULT_NODE_PANEL_PROPS,
    DEFAULT_VERTEX_PANEL_PROPS,
    build_rich_node_tree,
    build_rich_raw_table,
    build_rich_refs_box,
    build_rich_vertex_tree,
)
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec, QueryAnchorKind

configure_logging()
logger = logging.getLogger(__name__)


app = typer.Typer()


def _dump_raw_table(fetch_result: NodeFetchResult, console: Console, truncate: bool, show_transient: bool) -> None:
    """Print the raw-results Rich table for *fetch_result* to *console*.

    Delegates table construction to :func:`build_rich_raw_table`, then prints
    a section rule, a blank line, the table, and a row-count summary line.

    Args:
        fetch_result: Fetch result passed through to :func:`build_rich_raw_table`.
        console: Rich :class:`~rich.console.Console` to print to.
        truncate: When ``False``, render full (untruncated) cell values.
        show_transient: When ``True``, include the transient session/UI attribute columns.
    """
    raw_table: Final[Table] = build_rich_raw_table(fetch_result, truncate=truncate, show_transient=show_transient)
    console.rule("[bold]Raw Results[/bold]")
    console.print()
    console.print(raw_table)
    console.print(f"{raw_table.row_count} raw pull-block(s)")


def _dump_node_tree(fetch_result: NodeFetchResult, node_props: str | None, console: Console, truncate: bool) -> None:
    """Render and print the node tree from *fetch_result* as a Rich tree.

    Logs a warning and returns early when
    :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.anchor_tree` is ``None``.
    After the tree, prints a ``refs`` box containing one
    :func:`~guffin.render.rich_rendering.build_node_panel` panel per node in
    :attr:`~guffin.roam.node_tree.NodeTree.refs_by_id` (omitted when empty).

    Args:
        fetch_result: Fetch result whose :attr:`~guffin.roam.node_fetch_result.NodeFetchResult.anchor_tree`
            is rendered.
        node_props: Comma-separated :class:`~guffin.roam.node.RoamNode` field names
            to include in each panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_NODE_PANEL_PROPS`.
        console: Rich :class:`~rich.console.Console` to print to.
        truncate: When ``False``, render full (untruncated) panel strings.
    """
    if fetch_result.anchor_tree is None:
        logger.warning("show_node_tree=True but anchor_tree is None; skipping node tree output")
        return
    effective_props: Final[list[str]] = (
        [p.strip() for p in node_props.split(",")] if node_props is not None else list(DEFAULT_NODE_PANEL_PROPS)
    )
    node_rich_tree: Final[RichTree] = build_rich_node_tree(fetch_result.anchor_tree, effective_props, truncate=truncate)
    console.rule("[bold]Node Tree[/bold]")
    console.print()
    console.print(node_rich_tree)
    refs_box: Final[Panel | None] = build_rich_refs_box(fetch_result.anchor_tree, effective_props, truncate=truncate)
    if refs_box is not None:
        console.print(refs_box)
    console.print(
        f"{len(fetch_result.anchor_tree.tree_network)} node(s) in anchor tree, "
        f"{len(fetch_result.network)} total node(s) in fetch result"
    )


def _dump_vertex_tree(
    vertex_tree: VertexTree | None,
    vertex_props: str | None,
    api_endpoint: ApiEndpoint,
    console: Console,
    truncate: bool,
) -> None:
    """Fetch image sizes, enrich *vertex_tree*, then render and print it as a Rich tree.

    Logs a warning and returns early when *vertex_tree* is ``None``.  Otherwise
    fetches every asset-bearing vertex's file (to a temporary directory) via
    :func:`~guffin.render.asset_fetch.fetch_and_enrich_assets` so each image's
    :attr:`~guffin.vertex.ImageVertex.original_image_size` is populated before
    rendering.

    Args:
        vertex_tree: Normalized :class:`~guffin.vertex_tree.VertexTree` to render,
            or ``None`` when vertex tree computation was skipped.
        vertex_props: Comma-separated :class:`~guffin.vertex.Vertex` field names
            to include in each panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_VERTEX_PANEL_PROPS`.
        api_endpoint: Roam Local API endpoint used to fetch image assets for
            original-size enrichment.
        console: Rich :class:`~rich.console.Console` to print to.
        truncate: When ``False``, render full (untruncated) panel strings.
    """
    if vertex_tree is None:
        logger.warning("show_vertex_tree=True but vertex_tree is None; skipping vertex tree output")
        return
    with tempfile.TemporaryDirectory() as tmp:
        enriched_tree: Final[VertexTree] = fetch_and_enrich_assets(vertex_tree, api_endpoint, Path(tmp))[0]
    effective_props: Final[list[str]] = (
        [p.strip() for p in vertex_props.split(",")] if vertex_props is not None else list(DEFAULT_VERTEX_PANEL_PROPS)
    )
    vertex_rich_tree: Final[RichTree] = build_rich_vertex_tree(enriched_tree, effective_props, truncate=truncate)
    logger.debug("vertex_rich_tree=%r", vertex_rich_tree)
    console.rule("[bold]Vertex Tree[/bold]")
    console.print()
    console.print(vertex_rich_tree)
    console.print(f"{len(enriched_tree.tree_vertices)} vertices in vertex tree")


def dump_trees(
    fetch_result: NodeFetchResult,
    vertex_tree: VertexTree | None,
    node_props: str | None,
    vertex_props: str | None,
    api_endpoint: ApiEndpoint,
    show_raw_results: bool,
    show_node_tree: bool,
    show_vertex_tree: bool,
    truncate: bool,
    show_transient: bool,
) -> None:
    """Dispatch to the enabled display functions and print results to the console.

    Calls :func:`_dump_raw_table`, :func:`_dump_node_tree`, and/or
    :func:`_dump_vertex_tree` based on the corresponding flags.

    Args:
        fetch_result: The :class:`~guffin.roam.node_fetch_result.NodeFetchResult` returned
            by the fetch pipeline, carrying the raw node tree and Datalog results.
        vertex_tree: Normalized :class:`~guffin.vertex_tree.VertexTree` produced
            by :func:`~guffin.transcribe.roam_tree_to_guffin.transcribe`, or ``None`` when
            vertex tree computation was skipped.
        node_props: Comma-separated list of :class:`~guffin.roam.node.RoamNode`
            field names to include in each node panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_NODE_PANEL_PROPS`.
        vertex_props: Comma-separated list of :class:`~guffin.vertex.Vertex`
            field names to include in each vertex panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_VERTEX_PANEL_PROPS`.
        api_endpoint: Roam Local API endpoint (URL + bearer token), forwarded
            to :func:`_dump_vertex_tree`.
        show_raw_results: When ``True``, call :func:`_dump_raw_table`.
        show_node_tree: When ``True``, call :func:`_dump_node_tree`.
        show_vertex_tree: When ``True``, call :func:`_dump_vertex_tree`.
        truncate: When ``False``, render full (untruncated) string values in every view.
        show_transient: When ``True``, include the transient session/UI attribute columns in the
            raw-results table.
    """
    console: Final[Console] = Console()
    if show_raw_results:
        _dump_raw_table(fetch_result, console, truncate, show_transient)
    if show_node_tree:
        _dump_node_tree(fetch_result, node_props, console, truncate)
    if show_vertex_tree:
        _dump_vertex_tree(vertex_tree, vertex_props, api_endpoint, console, truncate)


@app.command()
def main(
    target: TargetArgument,
    local_api_port: PortOption,
    graph_name: GraphOption,
    api_bearer_token: TokenOption,
    node_props: Annotated[
        str | None,
        typer.Option(
            "--node-props",
            help=(
                "Comma-separated list of RoamNode property names to include in each panel body. "
                f"Example: --node-props heading,parents. "
                f"Defaults to: {','.join(DEFAULT_NODE_PANEL_PROPS)}. "
                'Unrecognized names are shown as "name=?" in the panel body.'
            ),
        ),
    ] = None,
    vertex_props: Annotated[
        str | None,
        typer.Option(
            "--vertex-props",
            help=(
                "Comma-separated list of Vertex property names to include in each panel body. "
                f"Example: --vertex-props type,children,text. "
                f"Defaults to: {','.join(DEFAULT_VERTEX_PANEL_PROPS)}. "
                'Unrecognized names are shown as "name=?" in the panel body.'
            ),
        ),
    ] = None,
    include_refs: Annotated[
        bool,
        typer.Option(
            "--include-refs/--no-include-refs",
            "-i/-I",
            help=(
                "When enabled, also fetches every node referenced via :block/refs "
                "from the target page or any of its descendants. "
                "Ignored when TARGET is a node UID."
            ),
        ),
    ] = True,
    show_raw_results: Annotated[
        bool,
        typer.Option(
            "--raw-results/--no-raw-results",
            "-r/-R",
            help="When enabled, print the raw Datalog query results.",
        ),
    ] = False,
    show_node_tree: Annotated[
        bool,
        typer.Option(
            "--node-tree/--no-node-tree",
            "-n/-N",
            help="When enabled, render and print the node tree.",
        ),
    ] = False,
    show_vertex_tree: Annotated[
        bool,
        typer.Option(
            "--vertex-tree/--no-vertex-tree",
            "-v/-V",
            help="When enabled, render and print the vertex tree.",
        ),
    ] = True,
    truncate: Annotated[
        bool,
        typer.Option(
            "--truncate/--no-truncate",
            help="When disabled (--no-truncate), render full string values in all output instead of "
            "shortening long strings with an ellipsis.",
        ),
    ] = True,
    show_transient: Annotated[
        bool,
        typer.Option(
            "--show-transient/--no-show-transient",
            help="In the raw-results table (--raw-results), also show the transient session/UI "
            "attribute columns (open, sidebar, edit/create timestamps and users, nonces, "
            "word-count) that are hidden by default. No effect without --raw-results.",
        ),
    ] = False,
) -> None:
    """Dump a Roam Research page or node subtree as a Rich tree to the console.

    TARGET is a Roam page title (optionally wrapped in ``[[ ]]``), a node UID, or a
    block reference ``((uid))``.  When wrapped in ``(( ))`` or matching the node-UID
    pattern, it fetches the subtree rooted at that node; otherwise it is treated as a
    page title and fetches all blocks on that page.

    Use ``--vertex-tree`` / ``-v/-V`` and ``--node-tree`` / ``-n/-N`` to control which
    trees are printed (vertex tree is shown by default).  Use ``--raw-results`` /
    ``-r/-R`` to also print the raw Datalog query results, and ``--show-transient`` to
    include the transient session/UI attribute columns (hidden by default) in that raw
    table.  Use ``--include-refs`` / ``-i/-I`` to additionally fetch nodes referenced via
    ``:block/refs`` from the target page or its descendants.  Use ``--no-truncate`` to
    render full string values across every view instead of shortening long strings with
    an ellipsis.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, api_bearer_token=%r, node_props=%r, vertex_props=%r, "
        "show_raw_results=%r, show_vertex_tree=%r, show_node_tree=%r, include_refs=%r, truncate=%r, "
        "show_transient=%r",
        target,
        local_api_port,
        graph_name,
        api_bearer_token,
        node_props,
        vertex_props,
        show_raw_results,
        show_vertex_tree,
        show_node_tree,
        include_refs,
        truncate,
        show_transient,
    )
    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=local_api_port,
        graph_name=graph_name,
        bearer_token=api_bearer_token,
    )

    fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
        anchor=NodeFetchAnchor(qualifier=target), include_refs=include_refs, include_node_tree=show_node_tree
    )
    try:
        trees: Final[tuple[NodeFetchResult, RenderBundle | None]] = fetch_roam_trees(
            fetch_spec, show_vertex_tree, api_endpoint
        )
    except RoamNodeNotFoundError as exc:
        kind_label: Final[str] = "Page" if exc.fetch_spec.anchor.kind == QueryAnchorKind.PAGE_TITLE else "Node"
        logger.error(
            "%s %r not found in Roam graph %r",
            kind_label,
            exc.fetch_spec.anchor.qualifier,
            graph_name,
        )
        raise typer.Exit(code=1)
    except Exception:
        logger.exception("Error fetching %r from graph %r", target, graph_name)
        raise typer.Exit(code=1)
    fetch_result: Final[NodeFetchResult] = trees[0]
    render_bundle: Final[RenderBundle | None] = trees[1]
    vertex_tree: Final[VertexTree | None] = render_bundle.content if render_bundle is not None else None
    dump_trees(
        fetch_result=fetch_result,
        vertex_tree=vertex_tree,
        node_props=node_props,
        vertex_props=vertex_props,
        api_endpoint=api_endpoint,
        show_raw_results=show_raw_results,
        show_node_tree=show_node_tree,
        show_vertex_tree=show_vertex_tree,
        truncate=truncate,
        show_transient=show_transient,
    )


if __name__ == "__main__":
    app()
