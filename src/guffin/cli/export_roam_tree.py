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
  ``<output_dir>/<target>.pdf``.  The ``--bundle/--no-bundle`` option does
  not apply and is ignored.  Pass
  ``--template-dir`` to supply a directory containing a ``user_cfg.typ``
  override for the bundled Bergfink Typst template.  Requires Pandoc and
  Typst to be installed.

- **EPUB** (``--format epub``) — builds a Pandoc object model directly from
  the :class:`~guffin.vertex_tree.VertexTree` via
  :func:`~guffin.render.epub_rendering.render` and writes
  ``<output_dir>/<target>.epub``.  The page title becomes the EPUB
  ``dc:title`` and top-level headings become the e-book's chapters; images
  are embedded into the package.  The ``--bundle/--no-bundle`` and
  ``--template-dir`` options do not apply and are ignored.  Requires Pandoc
  to be installed.

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

- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`main` — the CLI entry point; registered as the ``export-roam-tree``
  console script.

Example::

    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format pdf
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format pdf --template-dir ~/mytheme
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --format epub
    export-roam-tree "Test Article" -p 3333 -g SCFH -t tok -o ~/docs --no-bundle
    export-roam-tree wdMgyBiP9 -p 3333 -g SCFH -t tok -o ~/docs
    export-roam-tree "Test Article"  # reads all options from env vars
"""

import logging
import pathlib
from typing import Annotated, Final

import typer

from guffin.model.render_bundle import RenderBundle
from guffin.cli.logging_config import configure_logging
from guffin.render.epub_rendering import render as render_epub
from guffin.render.md_rendering import render as render_md
from guffin.render.pdf_rendering import render as render_pdf
from guffin.render.render_options import (
    EpubRenderOptions,
    MarkdownRenderOptions,
    OutputFormat,
    PdfRenderOptions,
)
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec, QueryAnchorKind
from guffin.cli.common import deduce_out_file_stem, fetch_roam_trees
from guffin.cli.params import GraphOption, PortOption, TargetArgument, TokenOption

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def main(
    target: TargetArgument,
    local_api_port: PortOption,
    graph_name: GraphOption,
    api_bearer_token: TokenOption,
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
                "via Pandoc (requires Pandoc + a PDF engine on PATH); 'epub' builds an "
                "EPUB 3 e-book via Pandoc (requires Pandoc on PATH)."
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
    suppress_attributes: Annotated[
        bool,
        typer.Option(
            "--suppress-attributes/--no-suppress-attributes",
            help=(
                "When enabled, omits Roam attribute assignments (<attribute>:: <value>, ...) "
                "from the exported document. Applies to both --format markdown and --format pdf."
            ),
        ),
    ] = False,
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

    TARGET is a Roam page title (optionally wrapped in ``[[ ]]``), a node UID, or a
    block reference ``((uid))``.  When wrapped in ``(( ))`` or matching the node-UID
    pattern, it fetches the subtree rooted at that node; otherwise it is treated as a
    page title and fetches all blocks on that page.

    With ``--format markdown`` (default): ``--bundle`` writes a
    ``<target>.mdbundle/`` directory with images; ``--no-bundle`` writes a
    plain ``<target>.md`` file.

    With ``--format pdf``: writes ``<target>.pdf`` via Pandoc + Typst using
    the bundled Bergfink template.  Pass ``--template-dir`` to a directory
    containing ``user_cfg.typ`` to override the default styling.  The
    ``--bundle/--no-bundle`` options are ignored.

    With ``--format epub``: writes ``<target>.epub`` via Pandoc.  The page
    title becomes the EPUB title and top-level headings become chapters.  The
    ``--bundle/--no-bundle`` and ``--template-dir`` options are ignored.
    """
    logger.debug(
        "target=%r, local_api_port=%r, graph_name=%r, output_dir=%r, "
        "output_format=%r, bundle=%r, cache_dir=%r, template_dir=%r, suppress_attributes=%r, dump_pandoc_ast=%r",
        target,
        local_api_port,
        graph_name,
        output_dir,
        output_format,
        bundle,
        cache_dir,
        template_dir,
        suppress_attributes,
        dump_pandoc_ast,
    )

    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
        local_api_port=local_api_port,
        graph_name=graph_name,
        bearer_token=api_bearer_token,
    )

    try:
        trees: Final[tuple[NodeFetchResult, RenderBundle | None]] = fetch_roam_trees(
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
    render_bundle: Final[RenderBundle | None] = trees[1]
    if render_bundle is None:
        logger.error("render_bundle is None; cannot export without a render bundle")
        raise typer.Exit(code=1)

    out_file_stem: Final[str] = deduce_out_file_stem(render_bundle.content)

    if output_format is OutputFormat.PDF:
        pdf_options: Final[PdfRenderOptions] = PdfRenderOptions(
            output_dir=output_dir,
            cache_dir=cache_dir,
            template_dir=template_dir,
            suppress_attributes=suppress_attributes,
            dump_pandoc_ast=dump_pandoc_ast,
        )
        try:
            render_pdf(render_bundle, out_file_stem, api_endpoint, pdf_options)
        except Exception as e:
            logger.error("Error rendering PDF for %r: %s", target, e)
            raise typer.Exit(code=1)
    elif output_format is OutputFormat.EPUB:
        epub_options: Final[EpubRenderOptions] = EpubRenderOptions(
            output_dir=output_dir,
            cache_dir=cache_dir,
            suppress_attributes=suppress_attributes,
            dump_pandoc_ast=dump_pandoc_ast,
        )
        try:
            render_epub(render_bundle, out_file_stem, api_endpoint, epub_options)
        except Exception as e:
            logger.error("Error rendering EPUB for %r: %s", target, e)
            raise typer.Exit(code=1)
    else:
        md_options: Final[MarkdownRenderOptions] = MarkdownRenderOptions(
            output_dir=output_dir,
            cache_dir=cache_dir,
            bundle=bundle,
            suppress_attributes=suppress_attributes,
            dump_pandoc_ast=dump_pandoc_ast,
        )
        try:
            render_md(render_bundle, out_file_stem, api_endpoint, md_options)
        except Exception as e:
            logger.error("Error rendering Markdown for %r: %s", target, e)
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
