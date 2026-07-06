"""Unit tests for guffin.render.pdf_rendering's PDF-embed preparation and Doc rewriting."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.

import shutil
from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
import pytest
from conftest import FIXTURES_PDF_DIR

from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.publishing_semantics import PdfRender
from guffin.model.vertex import PageVertex, PdfVertex, TextVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.render.asset_fetch import AssetRef
from guffin.render.pandoc_rendering import vertex_tree_to_pandoc
from guffin.render.pdf_rendering import _apply_pdf_embeds, _prepare_pdf_embeds, _typst_str

_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf.enc?alt=media&token=aaa"

_INLINE_TAG = AttributeAssignment(
    attribute=AttributeInstance(
        definition=Attribute(name="pdf-render", domain=AttributeDomain.GUFFIN),
        link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1"),
    ),
    values=(LiteralValue(value="inline"),),
)


def _pdf(
    uid: str,
    url: str = _URL_A,
    original_file_name: str | None = "dummy.pdf",
    inline: bool = False,
) -> PdfVertex:
    return PdfVertex(
        uid=uid,
        source=url,  # type: ignore[arg-type]
        file_name="a.pdf.enc",
        original_file_name=original_file_name,
        attribute_assignments=[_INLINE_TAG] if inline else None,
    )


def _dummy_ref(uid: str, tmp_path: Path, name: str, original_file_name: str | None = "dummy.pdf") -> AssetRef:
    """An AssetRef whose path is a copy of the dummy.pdf fixture under *name* in *tmp_path*."""
    target = tmp_path / name
    if not target.exists():
        shutil.copyfile(FIXTURES_PDF_DIR / "dummy.pdf", target)
    return AssetRef(uid=uid, path=target, size=None, original_file_name=original_file_name)


# ---------------------------------------------------------------------------
# TestTypstStr
# ---------------------------------------------------------------------------


class TestTypstStr:
    """_typst_str() quotes text as a Typst string literal."""

    def test_plain_text_is_quoted(self) -> None:
        """Ordinary text is wrapped in double quotes."""
        assert _typst_str("dummy.pdf") == '"dummy.pdf"'

    def test_quotes_and_backslashes_escaped(self) -> None:
        """Embedded quotes and backslashes are escaped."""
        assert _typst_str('a"b\\c') == '"a\\"b\\\\c"'


# ---------------------------------------------------------------------------
# TestPreparePdfEmbeds
# ---------------------------------------------------------------------------


class TestPreparePdfEmbeds:
    """_prepare_pdf_embeds() builds one spec per fetched PDF asset, keyed by source URL."""

    def test_spec_carries_path_pages_and_default_render(self, tmp_path: Path) -> None:
        """An untagged PDF yields a LINK spec carrying the fetched path and page count."""
        vertex = _pdf("pdfuid001")
        tree = VertexTree(tree_vertices=[vertex])
        ref = _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": ref})
        spec = specs[str(vertex.source)]
        assert spec.source_path == ref.path
        assert spec.pages == 1
        assert spec.render is PdfRender.LINK

    def test_inline_tag_selects_inline_render(self, tmp_path: Path) -> None:
        """A pdf-render:: inline tag yields an INLINE spec."""
        vertex = _pdf("pdfuid001", inline=True)
        tree = VertexTree(tree_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        assert specs[str(vertex.source)].render is PdfRender.INLINE

    def test_unfetched_pdf_is_skipped(self, tmp_path: Path) -> None:
        """A PDF vertex with no fetched asset contributes no spec."""
        tree = VertexTree(tree_vertices=[_pdf("pdfuid001")])
        assert _prepare_pdf_embeds(tree, {}) == {}


# ---------------------------------------------------------------------------
# TestApplyPdfEmbeds
# ---------------------------------------------------------------------------


@pytest.mark.pandoc
class TestApplyPdfEmbeds:
    """_apply_pdf_embeds() rewrites PDF-embed link paragraphs into their Typst form."""

    @staticmethod
    def _doc_and_specs(tmp_path: Path, inline: bool) -> tuple[pf.Doc, dict[str, object], str]:
        page = PageVertex(uid="page00001", title="Doc", children=["pdfuid001"])
        vertex = _pdf("pdfuid001", inline=inline)
        tree = VertexTree(tree_vertices=[page, vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        return doc, specs, str(vertex.source)

    def test_link_mode_drops_link_keeping_filename_text(self, tmp_path: Path) -> None:
        """A LINK embed is replaced by bare filename text — no attachment, no hyperlink.

        The link-placed embed follows its parent's BULLET layout, so the paragraph lives inside
        the bulleted list item.
        """
        doc, specs, _url = self._doc_and_specs(tmp_path, inline=False)
        _apply_pdf_embeds(doc, specs)  # type: ignore[arg-type]
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        item_blocks = list(list(blocks[0].content)[0].content)
        assert len(item_blocks) == 1
        assert isinstance(item_blocks[0], pf.Para)
        assert not any(isinstance(inline, pf.Link) for inline in item_blocks[0].content)
        assert pf.stringify(item_blocks[0]).strip() == "dummy.pdf"
        assert not any(isinstance(block, pf.RawBlock) for block in doc.content)

    def test_inline_mode_renders_pages_without_attachment(self, tmp_path: Path) -> None:
        """An INLINE embed is replaced by one image call per page and no attachment."""
        doc, specs, _url = self._doc_and_specs(tmp_path, inline=True)
        _apply_pdf_embeds(doc, specs)  # type: ignore[arg-type]
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.RawBlock)
        assert blocks[0].format == "typst"
        assert "#pdf.attach" not in blocks[0].text
        assert blocks[0].text.count("#image(") == 1
        assert "page: 1" in blocks[0].text
        assert "width: 100%" in blocks[0].text

    def test_prose_paragraph_with_link_untouched(self, tmp_path: Path) -> None:
        """A link inside surrounding prose is not a PDF embed and is left alone."""
        page = PageVertex(uid="page00001", title="Doc", children=["textuid01"])
        text = TextVertex(uid="textuid01", text=f"see [dummy.pdf]({_URL_A}) here")
        tree = VertexTree(tree_vertices=[page, text])
        pdf = _pdf("pdfuid001")
        specs = _prepare_pdf_embeds(
            VertexTree(tree_vertices=[pdf]), {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")}
        )
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        _apply_pdf_embeds(doc, specs)
        assert not any(isinstance(b, pf.RawBlock) for b in doc.content)
