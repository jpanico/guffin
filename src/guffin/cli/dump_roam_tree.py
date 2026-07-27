#!/usr/bin/env python3
"""CLI tool for dumping a Roam Research page or node subtree as a Rich tree to the terminal.

Fetches Roam nodes identified by ``TARGET`` via the Roam Local API and renders
one or more of the following as a colorized :class:`~rich.tree.Tree` panel
hierarchy:

- **Render bundle** (default, ``--render-bundle`` / ``-b/-B``) — the
  :class:`~guffin.model.render_bundle.RenderBundle` produced by
  :func:`~guffin.transcribe.roam_tree_to_guffin.to_render_bundle`, rendered as an outer panel over
  two sub-panels: the content :class:`~guffin.vertex_tree.VertexTree` (image vertices enriched with
  their native pixel size, fetched via the Local API, before display — pass ``--cache-dir`` to keep
  those downloads across runs) and the presentation
  :data:`~guffin.model.vertex_view.ViewMap` (as a tree of the vertices carrying a view entry, plus the
  ancestors connecting them to the root).
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
    dump-roam-tree "Test Article" -p 3333 -g SCFH -t tok -i -r -n -b
"""

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Final

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree as RichTree

from guffin.cli.common import fetch_roam_trees
from guffin.cli.logging_config import configure_logging
from guffin.cli.params import CacheDirOption, GraphOption, PortOption, TargetArgument, TokenOption
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ViewMap
from guffin.render.asset_fetch import fetch_and_enrich_assets
from guffin.render.rich_rendering import (
    DEFAULT_NODE_PANEL_PROPS,
    DEFAULT_VERTEX_PANEL_PROPS,
    build_rich_node_tree,
    build_rich_raw_table,
    build_rich_refs_box,
    build_rich_vertex_tree,
    build_rich_view_map_tree,
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


def _dump_render_bundle(
    render_bundle: RenderBundle | None,
    vertex_props: str | None,
    api_endpoint: ApiEndpoint,
    console: Console,
    truncate: bool,
    cache_dir: Path | None,
) -> None:
    """Enrich the bundle's content, then render it as a nested Rich panel of both its parts.

    Logs a warning and returns early when *render_bundle* is ``None``.  Otherwise fetches every
    asset-bearing vertex's file (to a temporary directory) via
    :func:`~guffin.render.asset_fetch.fetch_and_enrich_assets` so each image's
    :attr:`~guffin.vertex.ImageVertex.original_image_size` is populated before rendering, then prints
    an outer ``Render Bundle`` :class:`~rich.panel.Panel` holding two sub-panels: the content
    ``Vertex Tree`` (:func:`~guffin.render.rich_rendering.build_rich_vertex_tree`) followed by the
    presentation ``View Map`` (:func:`~guffin.render.rich_rendering.build_rich_view_map_tree`).

    Args:
        render_bundle: The :class:`~guffin.model.render_bundle.RenderBundle` to render, or ``None``
            when render-bundle computation was skipped.
        vertex_props: Comma-separated :class:`~guffin.vertex.Vertex` field names
            to include in each vertex panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_VERTEX_PANEL_PROPS`.
        api_endpoint: Roam Local API endpoint used to fetch image assets for
            original-size enrichment.
        console: Rich :class:`~rich.console.Console` to print to.
        truncate: When ``False``, render full (untruncated) panel strings.
        cache_dir: Directory caching downloaded assets across runs, or ``None`` to fetch
            every asset afresh.
    """
    if render_bundle is None:
        logger.warning("show_render_bundle=True but render_bundle is None; skipping render bundle output")
        return
    with tempfile.TemporaryDirectory() as tmp:
        enriched_tree: Final[VertexTree] = fetch_and_enrich_assets(
            render_bundle.content, api_endpoint, Path(tmp), cache_dir
        )[0]
    view_map: Final[ViewMap] = render_bundle.view
    effective_props: Final[list[str]] = (
        [p.strip() for p in vertex_props.split(",")] if vertex_props is not None else list(DEFAULT_VERTEX_PANEL_PROPS)
    )
    vertex_rich_tree: Final[RichTree] = build_rich_vertex_tree(enriched_tree, effective_props, truncate=truncate)
    view_rich_tree: Final[RichTree] = build_rich_view_map_tree(enriched_tree, view_map, truncate=truncate)
    logger.debug("vertex_rich_tree=%r, view_rich_tree=%r", vertex_rich_tree, view_rich_tree)
    bundle_panel: Final[Panel] = Panel(
        Group(
            Panel(vertex_rich_tree, title="[bold]Vertex Tree[/bold]", expand=False),
            Panel(view_rich_tree, title="[bold]View Map[/bold]", expand=False),
        ),
        title="[bold]Render Bundle[/bold]",
        expand=False,
    )
    console.rule("[bold]Render Bundle[/bold]")
    console.print()
    console.print(bundle_panel)
    console.print(f"{len(enriched_tree.tree_vertices)} vertices in vertex tree, {len(view_map)} entries in view map")


def dump_trees(
    fetch_result: NodeFetchResult,
    render_bundle: RenderBundle | None,
    node_props: str | None,
    vertex_props: str | None,
    api_endpoint: ApiEndpoint,
    show_raw_results: bool,
    show_node_tree: bool,
    show_render_bundle: bool,
    truncate: bool,
    show_transient: bool,
    cache_dir: Path | None = None,
) -> None:
    """Dispatch to the enabled display functions and print results to the console.

    Calls :func:`_dump_raw_table`, :func:`_dump_node_tree`, and/or
    :func:`_dump_render_bundle` based on the corresponding flags.

    Args:
        fetch_result: The :class:`~guffin.roam.node_fetch_result.NodeFetchResult` returned
            by the fetch pipeline, carrying the raw node tree and Datalog results.
        render_bundle: The :class:`~guffin.model.render_bundle.RenderBundle` (content
            :class:`~guffin.vertex_tree.VertexTree` plus presentation
            :data:`~guffin.model.vertex_view.ViewMap`) produced by
            :func:`~guffin.transcribe.roam_tree_to_guffin.to_render_bundle`, or ``None`` when
            render-bundle computation was skipped.
        node_props: Comma-separated list of :class:`~guffin.roam.node.RoamNode`
            field names to include in each node panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_NODE_PANEL_PROPS`.
        vertex_props: Comma-separated list of :class:`~guffin.vertex.Vertex`
            field names to include in each vertex panel body, or ``None`` to use
            :data:`~guffin.render.rich_rendering.DEFAULT_VERTEX_PANEL_PROPS`.
        api_endpoint: Roam Local API endpoint (URL + bearer token), forwarded
            to :func:`_dump_render_bundle`.
        show_raw_results: When ``True``, call :func:`_dump_raw_table`.
        show_node_tree: When ``True``, call :func:`_dump_node_tree`.
        show_render_bundle: When ``True``, call :func:`_dump_render_bundle`.
        truncate: When ``False``, render full (untruncated) string values in every view.
        show_transient: When ``True``, include the transient session/UI attribute columns in the
            raw-results table.
        cache_dir: Directory caching downloaded assets across runs, forwarded to
            :func:`_dump_render_bundle`; ``None`` (the default) fetches every asset afresh.
    """
    console: Final[Console] = Console()
    if show_raw_results:
        _dump_raw_table(fetch_result, console, truncate, show_transient)
    if show_node_tree:
        _dump_node_tree(fetch_result, node_props, console, truncate)
    if show_render_bundle:
        _dump_render_bundle(render_bundle, vertex_props, api_endpoint, console, truncate, cache_dir)


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
    show_render_bundle: Annotated[
        bool,
        typer.Option(
            "--render-bundle/--no-render-bundle",
            "-b/-B",
            help="When enabled, render and print the render bundle (vertex tree plus view map).",
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
    cache_dir: CacheDirOption = None,
    verify_code_sources_enabled: Annotated[
        bool,
        typer.Option(
            "--verify-code-sources/--no-verify-code-sources",
            envvar="GUFFIN_VERIFY_CODE_SOURCES",
            help=(
                "When enabled (the default), every code block carrying a code-source:: tag is "
                "verified against GitHub, with any mismatch or fetch failure reported as a "
                "warning — advisory only, the dump always renders. Requires the render bundle "
                "(--render-bundle). --no-verify-code-sources skips the check entirely (the "
                "offline path)."
            ),
        ),
    ] = True,
) -> None:
    """Dump a Roam Research page or node subtree as a Rich tree to the console.

    TARGET is a Roam page title (optionally wrapped in ``[[ ]]``), a node UID, or a
    block reference ``((uid))``.  When wrapped in ``(( ))`` or matching the node-UID
    pattern, it fetches the subtree rooted at that node; otherwise it is treated as a
    page title and fetches all blocks on that page.

    Use ``--render-bundle`` / ``-b/-B`` and ``--node-tree`` / ``-n/-N`` to control which
    trees are printed (the render bundle — vertex tree plus view map — is shown by default).  Use
    ``--raw-results`` / ``-r/-R`` to also print the raw Datalog query results, and ``--show-transient`` to
    include the transient session/UI attribute columns (hidden by default) in that raw
    table.  Use ``--include-refs`` / ``-i/-I`` to additionally fetch nodes referenced via
    ``:block/refs`` from the target page or its descendants.  Use ``--no-truncate`` to
    render full string values across every view instead of shortening long strings with
    an ellipsis.  Rendering the render bundle fetches every displayed asset (to read each
    image's native pixel size and each PDF's original filename); pass ``--cache-dir`` /
    ``-c`` to keep those downloads across runs.

    Code blocks carrying a ``code-source::`` tag are verified against GitHub by default
    (``--no-verify-code-sources`` skips the network check); any mismatch or fetch failure
    is reported as a warning — advisory only, the dump always renders.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, api_bearer_token=%r, node_props=%r, vertex_props=%r, "
        "show_raw_results=%r, show_render_bundle=%r, show_node_tree=%r, include_refs=%r, truncate=%r, "
        "show_transient=%r, cache_dir=%r",
        target,
        local_api_port,
        graph_name,
        api_bearer_token,
        node_props,
        vertex_props,
        show_raw_results,
        show_render_bundle,
        show_node_tree,
        include_refs,
        truncate,
        show_transient,
        cache_dir,
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
        # Both content gates (semantics validation and the optional code-source verification)
        # run advisorily here: findings warn, the dump always renders — this is the inspection
        # tool, not the publisher.
        trees: Final[tuple[NodeFetchResult, RenderBundle | None]] = fetch_roam_trees(
            fetch_spec, show_render_bundle, api_endpoint, verify_code_sources=verify_code_sources_enabled
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
    dump_trees(
        fetch_result=fetch_result,
        render_bundle=render_bundle,
        node_props=node_props,
        vertex_props=vertex_props,
        api_endpoint=api_endpoint,
        show_raw_results=show_raw_results,
        show_node_tree=show_node_tree,
        show_render_bundle=show_render_bundle,
        truncate=truncate,
        show_transient=show_transient,
        cache_dir=cache_dir,
    )


if __name__ == "__main__":
    app()
