"""Unit tests for guffin.render.pdf_rendering's PDF-embed preparation and Doc rewriting."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.
# pyright: reportPrivateUsage=false
# Rationale: these unit tests deliberately exercise module-private helpers (e.g.
# _prepare_pdf_embeds, _apply_pdf_embeds, _typst_str) directly.

import shutil
from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
import pytest
from conftest import FIXTURES_PDF_DIR, article3_node_tree

from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.publishing_semantics import PdfRender
from guffin.model.vertex import HeadingVertex, PageVertex, PdfVertex, TextVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.render.asset_fetch import AssetRef
from guffin.render.pandoc_ast import pandoc_to_json
from guffin.render.pandoc_rendering import vertex_tree_to_pandoc
from guffin.render.pdf_rendering import (
    _apply_pdf_embeds,
    _prepare_pdf_embeds,
    _prepare_title_metadata,
    _standalone_reference_renders,
    _typst_resources_dir,
    _typst_str,
    _typst_template_args,
)
from guffin.render.project import TopLevelDivision
from guffin.transcribe.roam_tree_to_guffin import transcribe

_URL_A = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf.enc?alt=media&token=aaa"


def _render_tag(value: str) -> AttributeAssignment:
    """A guffin pdf-render assignment carrying *value*."""
    return AttributeAssignment(
        attribute=AttributeInstance(
            definition=Attribute(name="pdf-render", domain=AttributeDomain.GUFFIN),
            link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1"),
        ),
        values=(LiteralValue(value=value),),
    )


_INLINE_TAG = _render_tag("inline")


def _reference_site(target_uid: str, render: str | None = None) -> TextVertex:
    """A text vertex whose entire text is a standalone vertex link to *target_uid*, optionally tagged."""
    return TextVertex(
        uid="refsite01",
        text=f"[a.pdf](x-guffin:vertex/{target_uid})",
        attribute_assignments=[_render_tag(render)] if render else None,
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

    def test_spec_carries_path_and_default_render_without_page_count(self, tmp_path: Path) -> None:
        """An untagged PDF yields a LINK spec carrying the fetched path and no page count."""
        vertex = _pdf("pdfuid001")
        tree = VertexTree(tree_vertices=[vertex])
        ref = _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": ref})
        spec = specs[str(vertex.source)]
        assert spec.source_path == ref.path
        assert spec.pages is None
        assert spec.render is PdfRender.LINK

    def test_inline_tag_selects_inline_render_with_page_count(self, tmp_path: Path) -> None:
        """A pdf-render:: inline tag yields an INLINE spec carrying the page count."""
        vertex = _pdf("pdfuid001", inline=True)
        tree = VertexTree(tree_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        spec = specs[str(vertex.source)]
        assert spec.render is PdfRender.INLINE
        assert spec.pages == 1

    def test_link_placement_never_parses_the_pdf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A LINK-placed PDF is never opened for a page count — the parse is INLINE's cost alone."""

        def _boom(path: str) -> None:
            raise AssertionError(f"PdfReader must not be invoked for a LINK placement (got {path!r})")

        monkeypatch.setattr("guffin.render.pdf_rendering.PdfReader", _boom)
        vertex = _pdf("pdfuid001")
        tree = VertexTree(tree_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        assert specs[str(vertex.source)].pages is None

    def test_unfetched_pdf_is_skipped(self, tmp_path: Path) -> None:
        """A PDF vertex with no fetched asset contributes no spec."""
        tree = VertexTree(tree_vertices=[_pdf("pdfuid001")])
        assert _prepare_pdf_embeds(tree, {}) == {}

    def test_reference_site_tag_selects_inline_render(self, tmp_path: Path) -> None:
        """A pdf-render:: inline tag at a standalone reference site governs the referenced PDF."""
        vertex = _pdf("pdfuid001")
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, _reference_site("pdfuid001", render="inline")], ref_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        spec = specs[str(vertex.source)]
        assert spec.render is PdfRender.INLINE
        assert spec.pages == 1

    def test_reference_site_tag_outranks_target_tag(self, tmp_path: Path) -> None:
        """The reference site is where this document displays the PDF, so its tag wins over the target's."""
        vertex = _pdf("pdfuid001", inline=True)
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, _reference_site("pdfuid001", render="link")], ref_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        spec = specs[str(vertex.source)]
        assert spec.render is PdfRender.LINK
        assert spec.pages is None

    def test_untagged_reference_site_falls_back_to_target_tag(self, tmp_path: Path) -> None:
        """An untagged reference site defers to the target PDF's own pdf-render tag."""
        vertex = _pdf("pdfuid001", inline=True)
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, _reference_site("pdfuid001")], ref_vertices=[vertex])
        specs = _prepare_pdf_embeds(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        assert specs[str(vertex.source)].render is PdfRender.INLINE

    def test_article3_fixture_reference_site_declares_inline(self) -> None:
        """The [[Test Article]] 3 fixture's site-tagged standalone PDF reference resolves to INLINE.

        The referenced PDF block lives on [[Test Article]] 1, so the fixture exercises the
        cross-page transclusion case end to end: the transcriber folds the ``pdf-render`` tag
        onto the reference-site text vertex, and the site's declaration reaches the embed
        preparation keyed by the target PDF's uid.
        """
        tree = transcribe(article3_node_tree())
        assert _standalone_reference_renders(tree) == {"pTvGGeTlB": PdfRender.INLINE}


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


class TestPrepareTitleMetadata:
    """_prepare_title_metadata() splits the title into a plain string and a rich display copy.

    ``title`` flattens to a plain string (the PDF ``/Title`` field and the running-header ``%title%``
    string machinery), while ``title-display`` keeps the rich inlines the template renders as content
    so a bold portion of the page name shows as markup in the running header.  The visible in-flow
    title is a separate body heading and keeps its emphasis regardless.
    """

    @staticmethod
    def _title_inlines() -> list[pf.Inline]:
        return [pf.Str("Doc"), pf.Space, pf.Strong(pf.Str("bold")), pf.Space, pf.Str("word")]

    @classmethod
    def _doc_with_bold_title(cls) -> pf.Doc:
        return pf.Doc(
            pf.Header(*cls._title_inlines(), level=1),
            metadata={"title": pf.MetaInlines(*cls._title_inlines())},
        )

    def test_plain_title_is_a_markup_free_string(self) -> None:
        """The `title` key flattens to a markup-free MetaString for /Title and %title% replacement."""
        doc = self._doc_with_bold_title()
        _prepare_title_metadata(doc)
        title = doc.metadata.content["title"]
        assert isinstance(title, pf.MetaString)
        assert title.text == "Doc bold word"

    def test_display_title_keeps_the_emphasis(self) -> None:
        """The `title-display` key keeps the rich inlines (a Strong) for content rendering."""
        doc = self._doc_with_bold_title()
        _prepare_title_metadata(doc)
        display = doc.metadata.content["title-display"]
        assert isinstance(display, pf.MetaInlines)
        assert any(isinstance(inline, pf.Strong) for inline in display.content)

    def test_body_heading_keeps_its_emphasis(self) -> None:
        """The visible in-flow title (a body Header) still carries its Strong."""
        doc = self._doc_with_bold_title()
        _prepare_title_metadata(doc)
        header = next(block for block in doc.content if isinstance(block, pf.Header))
        assert any(isinstance(inline, pf.Strong) for inline in header.content)

    def test_absent_title_is_a_noop(self) -> None:
        """A document with no title metadata key gains neither a plain nor a display title."""
        doc = pf.Doc(pf.Para(pf.Str("body")))
        _prepare_title_metadata(doc)
        assert "title" not in doc.metadata.content
        assert "title-display" not in doc.metadata.content


class TestTypstTemplateArgs:
    """_typst_template_args maps the cover image and revision name onto their Bergfink variables."""

    @staticmethod
    def _args(cover_image: Path | None, revision_name: str | None = None, emit_title_page: bool = True) -> list[str]:
        return _typst_template_args(
            bundled_dir=Path("/bundled"),
            template_path=Path("/bundled/bergfink.typst"),
            template_dir=None,
            number_sections=False,
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=emit_title_page,
            emit_toc=False,
            provenance=None,
            revision=None,
            revision_name=revision_name,
            cover_image=cover_image,
        )

    def test_cover_image_variable_passed(self) -> None:
        """A cover path becomes a -V cover-image=<path> pair."""
        args = self._args(Path("/tmp/assets/cover.jpg"))
        assert "cover-image=/tmp/assets/cover.jpg" in args
        assert args[args.index("cover-image=/tmp/assets/cover.jpg") - 1] == "-V"

    def test_no_cover_no_variable(self) -> None:
        """Without a cover path, no cover-image variable is passed."""
        assert not any(arg.startswith("cover-image=") for arg in self._args(None))

    def test_revision_variable_passed(self) -> None:
        """A revision name becomes a -V revision=<name> pair."""
        args = self._args(None, revision_name="draft-3")
        assert "revision=draft-3" in args
        assert args[args.index("revision=draft-3") - 1] == "-V"

    def test_no_revision_name_no_variable(self) -> None:
        """Without an authored revision name, no revision variable is passed."""
        assert not any(arg.startswith("revision=") for arg in self._args(None))

    def test_revision_variable_passed_without_title_page(self) -> None:
        """The running page header renders the name on every profile; no title page still passes it."""
        args = self._args(None, revision_name="draft-3", emit_title_page=False)
        assert "revision=draft-3" in args


# ---------------------------------------------------------------------------
# TestTypstPageBreakFilter
# ---------------------------------------------------------------------------


_PAGE_BREAK_TAG = AttributeAssignment(
    attribute=AttributeInstance(
        definition=Attribute(name="page-break", domain=AttributeDomain.GUFFIN),
        link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="attrpage1"),
    ),
    values=(LiteralValue(value="before"),),
)


@pytest.mark.pandoc
class TestTypstPageBreakFilter:
    """typst_page_break.lua opens a page-break-tagged heading on a new page in the Typst output."""

    @staticmethod
    def _typst_for(tagged: bool) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["head0001a"])
        heading = HeadingVertex(
            uid="head0001a",
            text="Breaking Section",
            heading_level=3,
            attribute_assignments=[_PAGE_BREAK_TAG] if tagged else None,
        )
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, heading]), {}, {})
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_page_break.lua'}"],
        )

    def test_tagged_heading_is_preceded_by_weak_pagebreak(self) -> None:
        """The tagged heading gains a weak Typst pagebreak ahead of it."""
        typst = self._typst_for(tagged=True)
        assert "#pagebreak(weak: true)" in typst
        assert typst.index("#pagebreak(weak: true)") < typst.index("Breaking Section")

    def test_untagged_heading_gains_no_pagebreak(self) -> None:
        """An untagged heading converts with no pagebreak."""
        assert "#pagebreak(weak: true)" not in self._typst_for(tagged=False)
