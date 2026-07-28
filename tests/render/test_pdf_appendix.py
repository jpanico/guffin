"""Tests for the shared appendix scaffolding and the EPUB appendix pass."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; the rules fire entirely on that Unknown propagation.
# pyright: reportPrivateUsage=false
# Rationale: these tests exercise the module-private EPUB pass (_apply_pdf_appendix) directly.

import shutil
from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
import pytest
from conftest import FIXTURES_PDF_DIR

from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.vertex import PageVertex, PdfVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.render.asset_fetch import AssetRef, pdf_asset_paths
from guffin.render.epub_rendering import PDF_PAGE_CLASS, _apply_pdf_appendix
from guffin.render.pandoc_rendering import vertex_tree_to_pandoc
from guffin.render.pdf_appendix import APPENDIX_ENTRY_CLASS, APPENDIX_ID, APPENDIX_TITLE
from guffin.render.pdf_raster import rasterize_pages
from guffin.render.project import ProjectType

pytestmark = pytest.mark.pandoc

_URL = "https://firebasestorage.googleapis.com/v0/b/t.appspot.com/o/pdfs%2Fa.pdf.enc?alt=media&token=a"


def _appendix_tag() -> AttributeAssignment:
    """A guffin ``pdf-render:: appendix-image`` assignment."""
    return AttributeAssignment(
        attribute=AttributeInstance(
            definition=Attribute(name="pdf-render", domain=AttributeDomain.GUFFIN),
            link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1"),
        ),
        values=(LiteralValue(value="appendix-image"),),
    )


class TestRasterizePages:
    """rasterize_pages() renders each page of a PDF to a PNG."""

    def test_writes_one_image_per_page(self, tmp_path: Path) -> None:
        """Every page becomes a distinctly named PNG, in page order."""
        images = rasterize_pages(FIXTURES_PDF_DIR / "dummy.pdf", tmp_path)
        assert [image.name for image in images] == ["dummy-p1.png"]
        assert all(image.exists() and image.stat().st_size > 0 for image in images)


class TestEpubPdfAppendix:
    """_apply_pdf_appendix() reproduces appendix-placed PDFs as rasterised pages at the back."""

    @staticmethod
    def _doc_and_paths(tmp_path: Path, uids: list[str]) -> tuple[pf.Doc, dict[str, Path]]:
        page = PageVertex(uid="page00001", title="Trip", children=uids)
        pdfs = [
            PdfVertex(
                uid=uid,
                source=_URL,  # type: ignore[arg-type]
                file_name="a.pdf.enc",
                original_file_name="dummy.pdf",
                attribute_assignments=[_appendix_tag()],
            )
            for uid in uids
        ]
        tree = VertexTree(tree_vertices=[page, *pdfs])
        target = tmp_path / "dummy.pdf"
        shutil.copyfile(FIXTURES_PDF_DIR / "dummy.pdf", target)
        refs = {uid: AssetRef(uid=uid, path=target, size=None, original_file_name="dummy.pdf") for uid in uids}
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        return doc, pdf_asset_paths(tree, refs)

    def test_pages_become_images_under_an_appendix(self, tmp_path: Path) -> None:
        """The embed becomes an internal link and the pages land as images in a back-matter section."""
        doc, paths = self._doc_and_paths(tmp_path, ["pdfuid001"])
        _apply_pdf_appendix(doc, paths, ProjectType.DEFAULT, tmp_path)
        headers = [b for b in doc.content if isinstance(b, pf.Header)]
        assert [h.level for h in headers] == [1, 2]
        assert pf.stringify(headers[0]) == APPENDIX_TITLE
        assert headers[0].identifier == APPENDIX_ID
        # Back matter, stamped directly since a generated section has no element-type tag to read.
        assert headers[0].attributes["epub:type"] == "appendix"
        assert all("unnumbered" in h.classes for h in headers)
        images: list[pf.Image] = []
        doc.walk(lambda e, d: images.append(e) if isinstance(e, pf.Image) else None)
        assert len(images) == 1
        assert Path(images[0].url).exists()
        # Styling hooks: epub.css bounds the page's height and asks the reader to keep the
        # heading with it, so the pages start under their own heading rather than overleaf.
        assert PDF_PAGE_CLASS in images[0].classes
        assert APPENDIX_ENTRY_CLASS in headers[1].classes

    def test_repeated_occurrences_share_one_entry(self, tmp_path: Path) -> None:
        """Two embeds of one PDF produce a single subsection that both anchors link to."""
        doc, paths = self._doc_and_paths(tmp_path, ["pdfuid001", "pdfuid002"])
        _apply_pdf_appendix(doc, paths, ProjectType.DEFAULT, tmp_path)
        headers = [b for b in doc.content if isinstance(b, pf.Header)]
        assert [h.level for h in headers] == [1, 2]
        links: list[pf.Link] = []
        doc.walk(lambda e, d: links.append(e) if isinstance(e, pf.Link) else None)
        assert len(links) == 2
        assert {link.url for link in links} == {f"#{headers[1].identifier}"}
