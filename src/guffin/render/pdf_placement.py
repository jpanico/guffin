"""Which :class:`~guffin.model.publishing_semantics.PdfRender` placement a format applies, and what it can honour.

The vocabulary in :mod:`~guffin.model.publishing_semantics` says what an author can *ask* for; it
is format-independent by design, so it holds no defaults.  What an untagged embed gets, and what
happens when a format cannot deliver what was asked, are render-layer decisions and live here.

Two policies:

- **The default.** An untagged embed's placement depends on the output being produced — the
  format, whether Markdown is bundling assets, and the kind of work.  A bundle can hand the reader
  the file itself; a lone ``.md`` can only point at where it is hosted; a book should carry its
  referenced documents rather than point away from them.  :func:`default_pdf_render` is that
  matrix.
- **The fallback.** Most of the vocabulary is not implemented in most formats yet.
  :func:`honoured_pdf_render` maps a requested placement to one the format actually supports,
  falling back to :data:`~guffin.model.publishing_semantics.PDF_RENDER_FALLBACK` and logging a
  warning whenever it cannot honour the request — including when the request came from the
  default policy rather than from an authored tag, since an unmet placement is worth knowing
  about either way.

Public symbols:

- :data:`SUPPORTED_PDF_RENDERS` — the placements each output target implements today.
- :func:`default_pdf_render` — the placement an untagged embed resolves to for an output target.
- :func:`requested_pdf_render` — the placement a stamped link asks for, defaulting when untagged.
- :func:`honoured_pdf_render` — a requested placement narrowed to one the target supports.
- :func:`apply_reference_placements` — resolve and apply every PDF placement, for a format that
  reproduces no pages.
- :func:`warn_unresolvable_external_link` — warn when an external link points at encrypted bytes.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

import logging
from collections.abc import Mapping
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
from pydantic import ConfigDict, validate_call

from guffin.model.publishing_semantics import PDF_RENDER_FALLBACK, PdfRender
from guffin.render.pandoc_rendering import PDF_PLACEMENT_ATTRIBUTE, PDF_PLACEMENT_UNSET
from guffin.render.project import ProjectType
from guffin.render.render_options import OutputFormat

logger = logging.getLogger(__name__)

_ENCRYPTED_ASSET_SUFFIX: Final[str] = ".enc"
"""The extension Roam appends to a hosted asset's storage key when the graph is encrypted."""

type _OutputTarget = tuple[OutputFormat, bool]
"""An output target: the format, plus whether Markdown is bundling its assets.

``should_bundle`` is meaningless outside Markdown and is ``True`` for the other formats, which
always carry their assets.
"""

SUPPORTED_PDF_RENDERS: Final[Mapping[_OutputTarget, frozenset[PdfRender]]] = {
    (OutputFormat.MARKDOWN, True): frozenset({PdfRender.INTERNAL_LINK, PdfRender.EXTERNAL_LINK, PdfRender.NAME_ONLY}),
    (OutputFormat.MARKDOWN, False): frozenset({PdfRender.EXTERNAL_LINK, PdfRender.NAME_ONLY}),
    (OutputFormat.PDF, True): frozenset(
        {PdfRender.INLINE_NATIVE, PdfRender.APPENDIX_NATIVE, PdfRender.EXTERNAL_LINK, PdfRender.NAME_ONLY}
    ),
    (OutputFormat.EPUB, True): frozenset({PdfRender.EXTERNAL_LINK, PdfRender.NAME_ONLY}),
}
"""The placements each output target implements today; every other request falls back.

A bundling Markdown export writes the asset beside the document, so it can link to a contained
copy; a plain ``.md`` has nowhere to put one.  The PDF path reproduces pages natively via Typst,
either at the embed or in a generated back-matter appendix linked from it.  No format renders
page images, and no format but PDF reproduces pages at all.
"""

_DEFAULT_PDF_RENDERS: Final[Mapping[tuple[OutputFormat, bool, ProjectType], PdfRender]] = {
    (OutputFormat.MARKDOWN, True, ProjectType.DEFAULT): PdfRender.INTERNAL_LINK,
    (OutputFormat.MARKDOWN, True, ProjectType.MANUSCRIPT): PdfRender.INTERNAL_LINK,
    (OutputFormat.MARKDOWN, True, ProjectType.BOOK): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.MARKDOWN, False, ProjectType.DEFAULT): PdfRender.EXTERNAL_LINK,
    (OutputFormat.MARKDOWN, False, ProjectType.MANUSCRIPT): PdfRender.EXTERNAL_LINK,
    (OutputFormat.MARKDOWN, False, ProjectType.BOOK): PdfRender.EXTERNAL_LINK,
    (OutputFormat.PDF, True, ProjectType.DEFAULT): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.PDF, True, ProjectType.MANUSCRIPT): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.PDF, True, ProjectType.BOOK): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.EPUB, True, ProjectType.DEFAULT): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.EPUB, True, ProjectType.MANUSCRIPT): PdfRender.APPENDIX_NATIVE,
    (OutputFormat.EPUB, True, ProjectType.BOOK): PdfRender.APPENDIX_IMAGE,
}
"""The placement an untagged embed resolves to, per output target and project type."""


@validate_call
def default_pdf_render(
    output_format: OutputFormat,
    project_type: ProjectType,
    should_bundle: bool = True,
) -> PdfRender:
    """Return the placement an untagged PDF embed resolves to for this output.

    The default is not a property of the vocabulary but of what is being produced: a bundling
    Markdown export can hand the reader the file itself, a lone ``.md`` can only point at where it
    is hosted, and a book carries its referenced documents rather than pointing away from them.

    Args:
        output_format: The format being rendered.
        project_type: The kind of work being produced.
        should_bundle: Whether a Markdown render is bundling its assets; ignored by the other
            formats, which always carry theirs.

    Returns:
        The :class:`~guffin.model.publishing_semantics.PdfRender` for an untagged embed.
    """
    bundling: Final[bool] = should_bundle if output_format is OutputFormat.MARKDOWN else True
    return _DEFAULT_PDF_RENDERS[(output_format, bundling, project_type)]


@validate_call
def honoured_pdf_render(
    requested: PdfRender,
    output_format: OutputFormat,
    uid: str,
    should_bundle: bool = True,
) -> PdfRender:
    """Return *requested* if this output supports it, else the fallback — logging a warning.

    Guffin never substitutes a placement it judges to be *closest* to the request: choosing among
    placements the author did not ask for is the author's call, so an unsupported request lands on
    :data:`~guffin.model.publishing_semantics.PDF_RENDER_FALLBACK` and says so.

    Args:
        requested: The placement resolved for this occurrence, whether authored or defaulted.
        output_format: The format being rendered.
        uid: The PDF vertex's UID, for the warning.
        should_bundle: Whether a Markdown render is bundling its assets.

    Returns:
        *requested* when supported, else
        :data:`~guffin.model.publishing_semantics.PDF_RENDER_FALLBACK`.
    """
    bundling: Final[bool] = should_bundle if output_format is OutputFormat.MARKDOWN else True
    supported: Final[frozenset[PdfRender]] = SUPPORTED_PDF_RENDERS[(output_format, bundling)]
    if requested in supported:
        return requested
    logger.warning(
        "pdf-render %r is not supported by %s output%s; falling back to %r for PDF uid=%r",
        requested.value,
        output_format.value,
        "" if output_format is not OutputFormat.MARKDOWN else (" (bundled)" if bundling else " (unbundled)"),
        PDF_RENDER_FALLBACK.value,
        uid,
    )
    return PDF_RENDER_FALLBACK


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def requested_pdf_render(
    link: pf.Link,
    output_format: OutputFormat,
    project_type: ProjectType,
    should_bundle: bool = True,
) -> PdfRender:
    """Return the placement *link* asks for: its authored stamp, else this output's default.

    Args:
        link: A PDF embed's link, stamped by the shared build with an authored placement or
            :data:`~guffin.render.pandoc_rendering.PDF_PLACEMENT_UNSET`.
        output_format: The format being rendered.
        project_type: The kind of work being produced.
        should_bundle: Whether a Markdown render is bundling its assets.

    Returns:
        The requested :class:`~guffin.model.publishing_semantics.PdfRender`, before any
        supported-placement narrowing (see :func:`honoured_pdf_render`).
    """
    stamped: Final[str] = link.attributes.get(PDF_PLACEMENT_ATTRIBUTE, PDF_PLACEMENT_UNSET)
    if stamped == PDF_PLACEMENT_UNSET:
        return default_pdf_render(output_format, project_type, should_bundle)
    return PdfRender(stamped)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def apply_reference_placements(
    doc: pf.Doc,
    output_format: OutputFormat,
    project_type: ProjectType,
    should_bundle: bool = True,
) -> None:
    """Resolve every PDF embed's placement for a format that reproduces no pages, in place.

    For formats whose only supported placements are references — a link to a contained copy, a
    link to the hosted original, or the bare filename — this applies the whole resolution in one
    pass: the authored stamp or this output's default, narrowed to what the format supports
    (warning on any fallback), then acted on.  A
    :attr:`~guffin.model.publishing_semantics.PdfRender.NAME_ONLY` occurrence is unwrapped to its
    label text; a link placement keeps its link, whose URL the shared build already pointed at
    either the bundled copy or the remote source.  The scaffold attribute is consumed either way,
    since Pandoc writers surface it in output.

    Args:
        doc: The Panflute document to rewrite.
        output_format: The format being rendered.
        project_type: The kind of work being produced.
        should_bundle: Whether a Markdown render is bundling its assets.
    """

    def _action(elem: pf.Element, doc: pf.Doc) -> list[pf.Block] | None:
        if not isinstance(elem, pf.Para) or len(list(elem.content)) != 1:
            return None
        link = list(elem.content)[0]
        if not isinstance(link, pf.Link) or PDF_PLACEMENT_ATTRIBUTE not in link.attributes:
            return None
        requested: Final[PdfRender] = requested_pdf_render(link, output_format, project_type, should_bundle)
        placement: Final[PdfRender] = honoured_pdf_render(
            requested, output_format, uid=str(link.title or link.url), should_bundle=should_bundle
        )
        del link.attributes[PDF_PLACEMENT_ATTRIBUTE]
        if placement is PdfRender.NAME_ONLY:
            return [pf.Para(*list(link.content))]
        if placement is PdfRender.EXTERNAL_LINK:
            warn_unresolvable_external_link(link.title, str(link.url))
        return None

    doc.walk(_action)


@validate_call
def warn_unresolvable_external_link(label: str | None, source: str) -> bool:
    """Warn when an external link points at Roam-encrypted bytes, and report whether it did.

    Roam appends ``.enc`` to a hosted asset's storage key when the graph is encrypted, so the URL
    serves ciphertext: the link resolves to nothing usable outside the Roam client.  The link is
    still rendered — whether to point at the original is the author's decision, and this only
    makes it an informed one.

    Args:
        label: The PDF's display label, for the warning.
        source: The asset's Cloud Firestore URL.

    Returns:
        ``True`` when the source names encrypted content (and a warning was logged).
    """
    if not source.split("?")[0].endswith(_ENCRYPTED_ASSET_SUFFIX):
        return False
    logger.warning(
        "external-link on %r points at Roam-encrypted content (%s), so it will not resolve " "outside the Roam client",
        label or source,
        _ENCRYPTED_ASSET_SUFFIX,
    )
    return True
