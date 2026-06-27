"""Render options carried from a front end to a rendering entry point.

An immutable bundle of the settings that drive an export, decoupled from any particular front
end so the options can be constructed and passed without pulling in CLI dependencies.

:class:`RenderOptions` holds the settings common to every output format (destination directory,
asset cache, AST dump).  Each format then has its own subclass carrying only the switches that
apply to it — :class:`MarkdownRenderOptions` (the ``bundle`` mode) and :class:`PdfRenderOptions`
(the Typst ``template_dir`` override) — tagged by an ``output_format`` discriminator.  A renderer
accepts its own subclass, so every field it receives is one it can act on.

This carries the destination and configuration knobs — not the remaining operands a render call
also needs (the content bundle, output filename stem, or API endpoint).

Public symbols:

- **Enumerations**: :class:`OutputFormat` — the supported output formats (markdown / pdf).
- **Models**: :class:`RenderOptions` — the format-independent base options;
  :class:`MarkdownRenderOptions` — Markdown (GFM) options; :class:`PdfRenderOptions` — PDF options.
"""

import enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OutputFormat(enum.StrEnum):
    """Output format for an exported document, used as the discriminator of the options subclasses.

    Attributes:
        MARKDOWN: Render to GFM (:class:`MarkdownRenderOptions`).
        PDF: Render directly to PDF via the Pandoc object model / Panflute (:class:`PdfRenderOptions`).
    """

    MARKDOWN = "markdown"
    PDF = "pdf"


class RenderOptions(BaseModel):
    """The format-independent options shared by every rendering entry point.

    A base for the per-format subclasses (:class:`MarkdownRenderOptions`, :class:`PdfRenderOptions`);
    not instantiated directly.

    Attributes:
        output_dir: Directory the exported document (file or bundle) is written into; created
            if it does not already exist.
        cache_dir: Optional directory for caching downloaded Cloud Firestore assets across
            runs; ``None`` disables caching.
        suppress_attributes: When ``True``, omit Roam attribute assignments
            (``<attribute>:: <value>, …``) from the rendered output.  Defaults to ``False``.
        dump_pandoc_ast: When ``True``, write the Pandoc JSON AST (the serialized Panflute
            document) to ``<output_dir>/<filename_stem>.pandoc.json`` before the Pandoc
            conversion step.  Defaults to ``False``.
    """

    model_config = ConfigDict(frozen=True)

    output_dir: Path = Field(..., description="Directory the exported document is written into.")
    cache_dir: Path | None = Field(default=None, description="Directory for caching downloaded Cloud Firestore assets.")
    suppress_attributes: bool = Field(
        default=False, description="Omit Roam attribute assignments from the rendered output."
    )
    dump_pandoc_ast: bool = Field(
        default=False, description="Write the Pandoc JSON AST alongside the output before conversion."
    )


class MarkdownRenderOptions(RenderOptions):
    """Options for rendering to GFM Markdown.

    Attributes:
        output_format: Always :attr:`OutputFormat.MARKDOWN` (the discriminator).
        bundle: When ``True`` (default), fetch Cloud Firestore images and write a self-contained
            ``.mdbundle`` directory; when ``False``, write a plain ``.md`` file with image
            references left as hyperlinks.
    """

    output_format: Literal[OutputFormat.MARKDOWN] = Field(
        default=OutputFormat.MARKDOWN, description="Discriminator identifying Markdown options."
    )
    bundle: bool = Field(
        default=True, description="Write a .mdbundle directory with embedded images (True) or plain .md."
    )


class PdfRenderOptions(RenderOptions):
    """Options for rendering to PDF via Pandoc + Typst.

    Attributes:
        output_format: Always :attr:`OutputFormat.PDF` (the discriminator).
        template_dir: Optional directory containing a ``user_cfg.typ`` override for the bundled
            Bergfink Typst template styling; ``None`` uses the bundled default.
    """

    output_format: Literal[OutputFormat.PDF] = Field(
        default=OutputFormat.PDF, description="Discriminator identifying PDF options."
    )
    template_dir: Path | None = Field(
        default=None, description="Directory holding a user_cfg.typ Typst styling override."
    )
