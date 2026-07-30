"""Unit tests for guffin.render.pdf_placement."""

import panflute as pf

from guffin.model.publishing_semantics import PdfRenderPlacement
from guffin.render.pandoc_rendering import PDF_PLACEMENT_ATTRIBUTE, PDF_PLACEMENT_UNSET
from guffin.render.pdf_placement import (
    SUPPORTED_PDF_RENDERS,
    apply_reference_placements,
    default_pdf_render,
    honoured_pdf_render,
    requested_pdf_render,
)
from guffin.render.project import ProjectType
from guffin.render.render_options import OutputFormat


def _stamped_link(stamped: str) -> pf.Link:
    """Return a PDF-embed link carrying *stamped* as its placement scaffold attribute."""
    return pf.Link(
        pf.Str("doc.pdf"),
        url="https://example.com/doc.pdf",
        attributes={PDF_PLACEMENT_ATTRIBUTE: stamped},
    )


class TestDefaultPdfRender:
    """Tests for default_pdf_render, including the per-export override."""

    def test_matrix_default_for_pdf_output(self) -> None:
        """An untagged embed in PDF output defaults to the back-matter appendix."""
        assert default_pdf_render(OutputFormat.PDF, ProjectType.ARTICLE) is PdfRenderPlacement.APPENDIX_NATIVE

    def test_matrix_default_for_unbundled_markdown(self) -> None:
        """A plain .md has nowhere to put a copy, so the default points at the hosted original."""
        placement = default_pdf_render(OutputFormat.MARKDOWN, ProjectType.ARTICLE, should_bundle=False)
        assert placement is PdfRenderPlacement.EXTERNAL_LINK

    def test_override_replaces_the_matrix(self) -> None:
        """An override resolves the untagged placement regardless of the built-in matrix."""
        placement = default_pdf_render(OutputFormat.PDF, ProjectType.ARTICLE, override=PdfRenderPlacement.INLINE_NATIVE)
        assert placement is PdfRenderPlacement.INLINE_NATIVE

    def test_none_override_defers_to_the_matrix(self) -> None:
        """A None override is the unset state: the matrix decides."""
        assert (
            default_pdf_render(OutputFormat.EPUB, ProjectType.BOOK, override=None) is PdfRenderPlacement.APPENDIX_IMAGE
        )


class TestRequestedPdfRender:
    """Tests for the stamp-over-override-over-matrix precedence."""

    def test_untagged_link_resolves_to_the_override(self) -> None:
        """With an override set, an untagged occurrence resolves to it, not the matrix."""
        placement = requested_pdf_render(
            _stamped_link(PDF_PLACEMENT_UNSET),
            OutputFormat.PDF,
            ProjectType.ARTICLE,
            default_override=PdfRenderPlacement.INLINE_NATIVE,
        )
        assert placement is PdfRenderPlacement.INLINE_NATIVE

    def test_authored_stamp_outranks_the_override(self) -> None:
        """An authored pdf-render tag always wins over the per-export default override."""
        placement = requested_pdf_render(
            _stamped_link(PdfRenderPlacement.NAME_ONLY.value),
            OutputFormat.PDF,
            ProjectType.ARTICLE,
            default_override=PdfRenderPlacement.INLINE_NATIVE,
        )
        assert placement is PdfRenderPlacement.NAME_ONLY

    def test_untagged_link_without_override_resolves_to_the_matrix(self) -> None:
        """With no override, an untagged occurrence gets the built-in default."""
        placement = requested_pdf_render(_stamped_link(PDF_PLACEMENT_UNSET), OutputFormat.PDF, ProjectType.ARTICLE)
        assert placement is PdfRenderPlacement.APPENDIX_NATIVE


class TestHonouredPdfRender:
    """Tests for the supported-placement narrowing an override flows through."""

    def test_supported_request_passes_through(self) -> None:
        """A placement the output implements is honoured as-is."""
        assert honoured_pdf_render(PdfRenderPlacement.APPENDIX_IMAGE, OutputFormat.EPUB, uid="doc.pdf") is (
            PdfRenderPlacement.APPENDIX_IMAGE
        )

    def test_unsupported_request_falls_back_to_name_only(self) -> None:
        """A placement the output cannot honour — however it was requested — falls back."""
        assert (
            honoured_pdf_render(PdfRenderPlacement.INLINE_IMAGE, OutputFormat.EPUB, uid="doc.pdf")
            is PdfRenderPlacement.NAME_ONLY
        )

    def test_strip_is_supported_by_every_output_target(self) -> None:
        """Removing an occurrence is universally implementable, so no target falls back on it."""
        for supported in SUPPORTED_PDF_RENDERS.values():
            assert PdfRenderPlacement.STRIP in supported


class TestApplyReferencePlacementsStrip:
    """apply_reference_placements removes a STRIP occurrence without leaving a trace."""

    def test_strip_removes_the_paragraph_and_its_emptied_list(self) -> None:
        """A stripped only-occurrence takes its emptied list item — and list — with it."""
        doc = pf.Doc(pf.BulletList(pf.ListItem(pf.Para(_stamped_link(PdfRenderPlacement.STRIP.value)))))
        stripped = apply_reference_placements(doc, OutputFormat.MARKDOWN, ProjectType.ARTICLE, should_bundle=False)
        assert list(doc.content) == []
        assert stripped == frozenset({"https://example.com/doc.pdf"})

    def test_strip_leaves_sibling_items_intact(self) -> None:
        """Stripping one list item never disturbs its populated siblings."""
        doc = pf.Doc(
            pf.BulletList(
                pf.ListItem(pf.Para(_stamped_link(PdfRenderPlacement.STRIP.value))),
                pf.ListItem(pf.Para(pf.Str("kept"))),
            )
        )
        apply_reference_placements(doc, OutputFormat.MARKDOWN, ProjectType.ARTICLE, should_bundle=False)
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        assert len(list(blocks[0].content)) == 1
        assert pf.stringify(doc).strip() == "kept"

    def test_strip_via_default_override_removes_an_untagged_occurrence(self) -> None:
        """--default-pdf-render strip removes every untagged occurrence."""
        doc = pf.Doc(pf.Para(_stamped_link(PDF_PLACEMENT_UNSET)))
        stripped = apply_reference_placements(
            doc,
            OutputFormat.MARKDOWN,
            ProjectType.ARTICLE,
            should_bundle=False,
            default_override=PdfRenderPlacement.STRIP,
        )
        assert list(doc.content) == []
        assert stripped == frozenset({"https://example.com/doc.pdf"})

    def test_url_with_a_surviving_occurrence_is_not_reported_stripped(self) -> None:
        """One stripped and one surviving occurrence of a URL: the file is still referenced."""
        doc = pf.Doc(
            pf.Para(_stamped_link(PdfRenderPlacement.STRIP.value)),
            pf.Para(_stamped_link(PdfRenderPlacement.NAME_ONLY.value)),
        )
        stripped = apply_reference_placements(doc, OutputFormat.MARKDOWN, ProjectType.ARTICLE, should_bundle=False)
        assert stripped == frozenset()
        assert pf.stringify(doc).strip() == "doc.pdf"

    def test_no_strips_reports_nothing(self) -> None:
        """A run with no stripped occurrence reports no removable URLs."""
        doc = pf.Doc(pf.Para(_stamped_link(PdfRenderPlacement.NAME_ONLY.value)))
        stripped = apply_reference_placements(doc, OutputFormat.MARKDOWN, ProjectType.ARTICLE, should_bundle=False)
        assert stripped == frozenset()
