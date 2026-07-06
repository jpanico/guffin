#!/usr/bin/env python3
"""CLI tool for exporting a Roam Research page or node subtree.

Fetches all descendant blocks identified by ``TARGET`` via the Roam Local API,
transcribes them into a :class:`~guffin.vertex_tree.VertexTree`, and writes the
result in one of three output formats controlled by ``--format``.  In every
format the output filename stem embeds the selected ``--type`` project profile as
a ``.<type>`` segment (e.g. ``Foo.book.pdf``):

- **Markdown** (default, ``--format markdown``) — renders the tree to
  GFM via :func:`~guffin.render.md_rendering.render`, then writes in one
  of two bundle modes:

  - **Bundle mode** (default, ``--bundle``) — fetches Cloud Firestore images
    and writes a self-contained ``<output_dir>/<target>.<type>.mdbundle/``
    directory.  Pass ``--cache-dir`` to avoid re-downloading unchanged assets
    across runs.
  - **Plain mode** (``--no-bundle``) — writes the GFM text directly
    to ``<output_dir>/<target>.<type>.md``.

- **PDF** (``--format pdf``) — builds a Pandoc object model directly from
  the :class:`~guffin.vertex_tree.VertexTree` via
  :func:`~guffin.render.pdf_rendering.render` and writes
  ``<output_dir>/<target>.<type>.pdf``.  The ``--bundle/--no-bundle`` option does
  not apply and is ignored.  Pass
  ``--template-dir`` to supply a directory containing a ``user_cfg.typ``
  override for the bundled Bergfink Typst template.  Requires Pandoc and
  Typst to be installed.

- **EPUB** (``--format epub``) — builds a Pandoc object model directly from
  the :class:`~guffin.vertex_tree.VertexTree` via
  :func:`~guffin.render.epub_rendering.render` and writes
  ``<output_dir>/<target>.<type>.epub``.  The page title becomes the EPUB
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

Logging is colorized by level via :mod:`guffin.cli.logging_config` and
configurable via the ``LOG_LEVEL`` environment variable (default: ``INFO``).

Public symbols:

- :data:`app` — the :class:`~typer.Typer` application instance.
- :func:`fetch_render_bundle` — fetch a target's transcribed
  :class:`~guffin.model.render_bundle.RenderBundle` from a Roam graph.
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
from pydantic import validate_call

from guffin.cli.common import SemanticsValidationError, deduce_out_file_stem, fetch_roam_trees, resolve_profile
from guffin.cli.logging_config import configure_logging
from guffin.cli.params import GraphOption, PortOption, TargetArgument, TokenOption
from guffin.common.provenance import Provenance, gather_provenance
from guffin.model.render_bundle import RenderBundle
from guffin.render.epub_rendering import render as render_epub
from guffin.render.md_rendering import render as render_md
from guffin.render.pdf_rendering import render as render_pdf
from guffin.render.project import ProjectProfile, ProjectType
from guffin.render.render_options import (
    EpubRenderOptions,
    MarkdownRenderOptions,
    OutputFormat,
    PdfRenderOptions,
    RenderOptions,
)
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec, QueryAnchorKind

configure_logging()
logger = logging.getLogger(__name__)

app = typer.Typer()

_SECRET_PARAMS: Final[frozenset[str]] = frozenset({"api_bearer_token"})
"""``main`` parameter names excluded from the debug args log so secrets never reach the logs."""


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
    project_type: Annotated[
        ProjectType,
        typer.Option(
            "--type",
            "-T",
            help=(
                "Kind of work to produce: "
                + ", ".join(f"'{member.value}' ({member.description})" for member in ProjectType)
                + ". Selects the project profile; its structural effects apply to all formats."
            ),
        ),
    ] = ProjectType.DEFAULT,
    should_bundle: Annotated[
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
    colophon: Annotated[
        bool,
        typer.Option(
            "--colophon/--no-colophon",
            envvar="GUFFIN_EMIT_COLOPHON",
            help=(
                "When enabled (default), embeds an end-of-document provenance colophon recording "
                "the source git commit (hash + commit time, with a -dirty marker for uncommitted "
                "changes) and the export time, so any output document traces back to its exact "
                "source. Applies to all formats."
            ),
        ),
    ] = True,
    preamble: Annotated[
        bool | None,
        typer.Option(
            "--preamble/--no-preamble",
            envvar="GUFFIN_INCLUDE_PREAMBLE",
            help=(
                "PDF and EPUB only. Keep (--preamble) or drop (--no-preamble) the root page's "
                "loose preamble: children preceding its first heading, which belong to no titled "
                "division. Unset (default), the --type profile decides: 'book' drops the "
                "preamble, other types keep it. Ignored when --format markdown."
            ),
        ),
    ] = None,
    numbering: Annotated[
        bool | None,
        typer.Option(
            "--numbering/--no-numbering",
            envvar="GUFFIN_NUMBER_SECTIONS",
            help=(
                "PDF and EPUB only. Turn all heading numbering on (--numbering) or off "
                "(--no-numbering). Unset (default), the --type profile decides: 'book' numbers "
                "its headings, other types do not. Ignored when --format markdown."
            ),
        ),
    ] = None,
) -> None:
    """Export a Roam Research page or node subtree to Markdown, PDF, or EPUB.

    TARGET is a Roam page title (optionally wrapped in ``[[ ]]``), a node UID, or a
    block reference ``((uid))``.  When wrapped in ``(( ))`` or matching the node-UID
    pattern, it fetches the subtree rooted at that node; otherwise it is treated as a
    page title and fetches all blocks on that page.

    In every format the output filename stem embeds the selected ``--type`` as a
    ``.<type>`` segment, so the same target exported under different project types lands
    in distinct files — e.g. ``<target>.default.epub``, ``<target>.book.pdf``.

    With ``--format markdown`` (default): ``--bundle`` writes a
    ``<target>.<type>.mdbundle/`` directory with images; ``--no-bundle`` writes a
    plain ``<target>.<type>.md`` file.

    With ``--format pdf``: writes ``<target>.<type>.pdf`` via Pandoc + Typst using
    the bundled Bergfink template.  Pass ``--template-dir`` to a directory
    containing ``user_cfg.typ`` to override the default styling.  The
    ``--bundle/--no-bundle`` options are ignored.

    With ``--format epub``: writes ``<target>.<type>.epub`` via Pandoc.  The page
    title becomes the EPUB title and top-level headings become chapters.  The
    ``--bundle/--no-bundle`` and ``--template-dir`` options are ignored.
    """
    # Captured as the first statement so locals() is exactly the CLI parameters; the bearer token
    # is filtered out (see _SECRET_PARAMS) so it never reaches the logs.
    cli_args: Final[dict[str, object]] = locals()
    logger.debug("args: %r", {name: value for name, value in cli_args.items() if name not in _SECRET_PARAMS})

    api_endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port, graph_name, api_bearer_token)

    # An export must not publish content that violates the guffin vocabulary, so semantics
    # validation is strict here (dump-roam-tree keeps it advisory).
    fetched_bundle: Final[RenderBundle] = fetch_render_bundle(api_endpoint, target, strict_semantics=True)

    # The colophon's data (provenance) is stamped onto the bundle as origin metadata; whether to
    # render it is the separate emit_colophon option carried on the render options.
    provenance: Final[Provenance | None] = gather_provenance(extra={"type": project_type.value}) if colophon else None
    if provenance is not None:
        logger.info("provenance: %s", provenance.summary())
    render_bundle: Final[RenderBundle] = fetched_bundle.with_provenance(provenance)

    out_file_stem: Final[str] = deduce_out_file_stem(render_bundle.content, project_type)
    # A book whose content declares parts (a level-1 `element-type:: part` heading) becomes a
    # parts book; the content itself, not a CLI switch, is the source of that structure.
    profile: Final[ProjectProfile] = resolve_profile(project_type, render_bundle.content)
    options: Final[RenderOptions] = RenderOptions.for_format(
        output_format,
        output_dir=output_dir,
        cache_dir=cache_dir,
        template_dir=template_dir,
        should_bundle=should_bundle,
        suppress_attributes=suppress_attributes,
        dump_pandoc_ast=dump_pandoc_ast,
        emit_colophon=colophon,
        include_preamble=preamble,
        number_sections=numbering,
    )

    _render(render_bundle, profile, out_file_stem, api_endpoint, target, options)


@validate_call
def fetch_render_bundle(api_endpoint: ApiEndpoint, target: TargetArgument, strict_semantics: bool) -> RenderBundle:
    """Fetch *target* from a Roam graph and return its transcribed render bundle.

    Resolves *target* against *api_endpoint* (following references), runs guffin-semantics
    validation at the requested strictness, and unwraps the :class:`~guffin.model.render_bundle.RenderBundle`
    from the fetch result.

    Args:
        api_endpoint: The Roam Local API endpoint identifying the graph and bearer token.
        target: The page title, node UID, or ``((uid))`` block reference to fetch.
        strict_semantics: When ``True``, a guffin-vocabulary violation aborts the fetch; when
            ``False``, violations are advisory (logged, not fatal).

    Returns:
        The :class:`~guffin.model.render_bundle.RenderBundle` transcribed from *target*'s subtree.

    Raises:
        typer.Exit: With code 1 when the target is not found, the content fails strict semantics
            validation, any other fetch error occurs, or no render bundle is produced.
    """
    graph_name: Final[str] = api_endpoint.url.graph_name
    try:
        trees: Final[tuple[NodeFetchResult, RenderBundle | None]] = fetch_roam_trees(
            NodeFetchSpec(anchor=NodeFetchAnchor(qualifier=target), include_refs=True),
            include_vertex_tree=True,
            api_endpoint=api_endpoint,
            strict_semantics=strict_semantics,
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
    except SemanticsValidationError as exc:
        for validation_error in exc.result.errors:
            logger.error("guffin semantics validation: %s", validation_error)
        logger.error("aborting export of %r: the content violates the guffin vocabulary (see above)", target)
        raise typer.Exit(code=1)
    except Exception:
        logger.exception("Error fetching %r from graph %r", target, graph_name)
        raise typer.Exit(code=1)
    fetched_bundle: Final[RenderBundle | None] = trees[1]
    if fetched_bundle is None:
        logger.error("render_bundle is None; cannot export without a render bundle")
        raise typer.Exit(code=1)
    return fetched_bundle


def _render(
    render_bundle: RenderBundle,
    profile: ProjectProfile,
    filename_stem: str,
    api_endpoint: ApiEndpoint,
    target: str,
    options: RenderOptions,
) -> None:
    """Dispatch *render_bundle* to the renderer matching *options*' concrete type; exit 1 on failure.

    *options* is the format-specific :class:`~guffin.render.render_options.RenderOptions` subclass
    built by :meth:`~guffin.render.render_options.RenderOptions.for_format`; its type selects the
    renderer.  *profile* (the project type and bibliographic metadata) is passed through to it.  Any
    rendering failure is logged and turned into a :class:`typer.Exit` with code 1.
    """
    try:
        if isinstance(options, PdfRenderOptions):
            render_pdf(render_bundle, profile, filename_stem, api_endpoint, options)
        elif isinstance(options, EpubRenderOptions):
            render_epub(render_bundle, profile, filename_stem, api_endpoint, options)
        elif isinstance(options, MarkdownRenderOptions):
            render_md(render_bundle, profile, filename_stem, api_endpoint, options)
        else:
            raise TypeError(f"unsupported render options type: {type(options).__name__}")
    except Exception as e:
        logger.error("Error rendering %s for %r: %s", type(options).__name__, target, e)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
