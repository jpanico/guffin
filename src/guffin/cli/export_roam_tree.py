#!/usr/bin/env python3
"""CLI tool for exporting a Roam Research page or node subtree.

Fetches all descendant blocks identified by ``TARGET`` via the Roam Local API,
transcribes them into a :class:`~guffin.vertex_tree.VertexTree`, and writes the
result in one of two output formats controlled by ``--format``:

- **Markdown** (default, ``--format markdown``) — renders the tree to
  GFM via :func:`~guffin.render.md_rendering.vertex_tree_to_md`, then writes in one
  of two bundle modes:

  - **Bundle mode** (default, ``--bundle``) — fetches Cloud Firestore images
    and writes a self-contained ``<output_dir>/<target>.mdbundle/`` directory
    via :func:`~guffin.render.md_rendering.bundle_md_document`.  Pass
    ``--cache-dir`` to avoid re-downloading unchanged assets across runs.
  - **Plain mode** (``--no-bundle``) — writes the GFM text directly
    to ``<output_dir>/<target>.md``.

- **PDF** (``--format pdf``) — builds a Pandoc object model directly from
  the :class:`~guffin.vertex_tree.VertexTree` via
  :func:`~guffin.render.pdf_rendering.render_pdf` and writes
  ``<output_dir>/<target>.pdf``.  The ``--bundle/--no-bundle`` and
  ``--cache-dir`` options do not apply and are ignored.  Pass
  ``--template-dir`` to supply a directory containing a ``user_cfg.typ``
  override for the bundled Bergfink Typst template.  Requires Pandoc and
  Typst to be installed.

``TARGET`` is interpreted as a **node UID** if it matches
:data:`~guffin.roam.primitives.ANCHORED_UID_PATTERN` (exactly 9 alphanumeric/dash/underscore
characters, the fixed format used by Roam for all block and page UIDs); otherwise it is
treated as a **page title**.  A page whose title happens to be exactly 9
characters from that alphabet would be misidentified — this edge case is
considered negligible in practice.

Logging is colorized by level via :mod:`guffin.logging_config` and
configurable via the ``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :class:`OutputFormat` — output format enum (``markdown``, ``pdf``).
- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``export-roam-tree``
  console script.

Example::

    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format pdf
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format pdf --template-dir ~/mytheme
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --no-bundle
    export-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article"  # reads all options from env vars
"""

import enum
import logging
import pathlib
from typing import Annotated, Final

import typer

from guffin.vertex_tree import VertexTree
from guffin.cli.logging_config import configure_logging
from guffin.render.md_rendering import render as render_md
from guffin.render.pdf_rendering import render as render_pdf
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec, QueryAnchorKind
from guffin.roam.primitives import ANCHORED_UID_PATTERN
from guffin.cli.fetch_roam_tree import fetch_roam_trees

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()


class OutputFormat(enum.StrEnum):
    """Output format for the exported document.

    Values:
        MARKDOWN: Render to GFM; supports ``--bundle/--no-bundle``.
        PDF: Render directly to PDF via the Pandoc object model (Panflute);
            ``--bundle/--no-bundle`` and ``--cache-dir`` do not apply.
    """

    MARKDOWN = "markdown"
    PDF = "pdf"


@app.command()
def main(
    target: Annotated[
        str,
        typer.Argument(
            help=(
                "Roam page title or node UID to export. "
                f"Treated as a node UID if it matches {ANCHORED_UID_PATTERN}; "
                "otherwise treated as a page title."
            ),
        ),
    ],
    local_api_port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            envvar="GUFFIN_ROAM_LOCAL_API_PORT",
            help="Port for Roam Local API",
        ),
    ],
    graph_name: Annotated[
        str,
        typer.Option(
            "--graph",
            "-g",
            envvar="GUFFIN_ROAM_GRAPH_NAME",
            help="Name of the Roam graph",
        ),
    ],
    api_bearer_token: Annotated[
        str,
        typer.Option(
            "--token",
            "-t",
            envvar="GUFFIN_ROAM_API_TOKEN",
            help="Bearer token for Roam Local API authentication",
        ),
    ],
    output_dir: Annotated[
        pathlib.Path,
        typer.Option(
            "--output-dir",
            "-o",
            envvar="GUFFIN_EXPORT_DIR",
            help="Directory to write the exported document into.",
        ),
    ],
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help=(
                "Output format: 'markdown' (default) renders to GFM and supports "
                "--bundle/--no-bundle; 'pdf' builds a PDF directly from the vertex tree "
                "via Pandoc (requires Pandoc + a PDF engine on PATH)."
            ),
        ),
    ] = OutputFormat.MARKDOWN,
    bundle: Annotated[
        bool,
        typer.Option(
            "--bundle/--no-bundle",
            help=(
                "Markdown only. When enabled (default), fetches Cloud Firestore images "
                "and writes a .mdbundle directory. When disabled, writes a plain .md file. "
                "Ignored when --format pdf."
            ),
        ),
    ] = True,
    cache_dir: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--cache-dir",
            "-c",
            envvar="GUFFIN_CACHE_DIR",
            help=(
                "Directory for caching downloaded Cloud Firestore assets across runs. "
                "Applies to both --format markdown (bundle mode) and --format pdf."
            ),
        ),
    ] = None,
    template_dir: Annotated[
        pathlib.Path | None,
        typer.Option(
            "--template-dir",
            envvar="GUFFIN_PDF_TEMPLATE_DIR",
            help=(
                "PDF only. Directory containing a user_cfg.typ file that overrides the "
                "bundled Bergfink Typst template styling. Ignored when --format markdown."
            ),
        ),
    ] = None,
    dump_pandoc_ast: Annotated[
        bool,
        typer.Option(
            "--dump-pandoc-ast/--no-dump-pandoc-ast",
            envvar="GUFFIN_DUMP_PANDOC_AST",
            help=(
                "When enabled, writes the Pandoc JSON AST (serialized Panflute Doc) to "
                "<output-dir>/<target>.pandoc.json before the Pandoc conversion step. "
                "Applies to both --format markdown and --format pdf."
            ),
        ),
    ] = False,
) -> None:
    """Export a Roam Research page or node subtree to Markdown or PDF.

    TARGET is interpreted as a node UID (fetches the subtree rooted there) if
    it matches ``^[A-Za-z0-9_-]{9}$``, otherwise as a page title (fetches all
    blocks on that page).

    With ``--format markdown`` (default): ``--bundle`` writes a
    ``<target>.mdbundle/`` directory with images; ``--no-bundle`` writes a
    plain ``<target>.md`` file.

    With ``--format pdf``: writes ``<target>.pdf`` via Pandoc + Typst using
    the bundled Bergfink template.  Pass ``--template-dir`` to a directory
    containing ``user_cfg.typ`` to override the default styling.  The
    ``--bundle/--no-bundle`` options are ignored.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, output_dir=%r, "
        "output_format=%r, bundle=%r, cache_dir=%r, template_dir=%r, dump_pandoc_ast=%r",
        target,
        local_api_port,
        graph_name,
        output_dir,
        output_format,
        bundle,
        cache_dir,
        template_dir,
        dump_pandoc_ast,
    )

    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=local_api_port,
        graph_name=graph_name,
        bearer_token=api_bearer_token,
    )

    try:
        trees: Final[tuple[NodeFetchResult, VertexTree | None]] = fetch_roam_trees(
            NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=target), include_refs=True), True, api_endpoint
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
    vertex_tree: Final[VertexTree | None] = trees[1]
    if vertex_tree is None:
        logger.error("vertex_tree is None; cannot export without a vertex tree")
        raise typer.Exit(code=1)

    if output_format is OutputFormat.PDF:
        try:
            render_pdf(vertex_tree, target, output_dir, api_endpoint, cache_dir, template_dir, dump_pandoc_ast)
        except Exception as e:
            logger.error("Error rendering PDF for %r: %s", target, e)
            raise typer.Exit(code=1)
    else:
        try:
            render_md(vertex_tree, target, output_dir, api_endpoint, cache_dir, bundle, dump_pandoc_ast)
        except Exception as e:
            logger.error("Error rendering Markdown for %r: %s", target, e)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
