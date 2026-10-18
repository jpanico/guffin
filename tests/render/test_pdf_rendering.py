"""Unit tests for guffin.render.pdf_rendering's PDF-embed preparation and Doc rewriting."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.
# pyright: reportPrivateUsage=false
# Rationale: these unit tests deliberately exercise module-private helpers (e.g.
# pdf_asset_paths, _apply_pdf_embeds, _typst_str) directly.

import shutil
from pathlib import Path
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
import pypdfium2 as pdfium  # type: ignore[import-untyped]
import pypdfium2.raw as pdfium_raw  # type: ignore[import-untyped]
import pytest
from conftest import FIXTURES_IMAGES_DIR, FIXTURES_PDF_DIR, article3_node_tree, asset_storage
from pypdf import PdfReader

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.alternative import Alternative
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import (
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    PdfVertex,
    QuoteBlockVertex,
    QuoteType,
    TextVertex,
    TodoState,
    TodoVertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, Semantic, SourceChannel, VertexView, ViewMap
from guffin.render.asset_fetch import AssetRef, pdf_asset_paths
from guffin.render.pandoc_ast import pandoc_to_json
from guffin.render.pandoc_rendering import (
    PDF_PLACEMENT_ATTRIBUTE,
    PDF_PLACEMENT_UNSET,
    heading_anchor,
    vertex_tree_to_pandoc,
)
from guffin.render.pdf_rendering import (
    _apply_pdf_embeds,
    _prepare_title_metadata,
    _typst_resources_dir,
    _typst_str,
    _typst_template_args,
    pdf_asset_paths,
    render,
)
from guffin.render.project import ArticleProfile, BookProfile, ProjectType, TopLevelDivision
from guffin.render.render_options import PdfRenderOptions
from guffin.roam.local_api import ApiEndpoint
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


_INLINE_TAG = _render_tag("inline-native")


def _reference_site(target_uid: str, render: str | None = None, uid: str = "refsite01") -> TextVertex:
    """A text vertex whose entire text is a standalone vertex link to *target_uid*, optionally tagged."""
    return TextVertex(
        uid=uid,
        text=f"[a.pdf](x-guffin:vertex/{target_uid})",
        attribute_assignments=[_render_tag(render)] if render else None,
    )


def _pdf(
    uid: str,
    url: str = _URL_A,
    file_name: str | None = "dummy.pdf",
    inline: bool = False,
) -> PdfVertex:
    return PdfVertex(
        uid=uid,
        storage=asset_storage(url),
        file_name=file_name,
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
# TestPdfAssetPaths
# ---------------------------------------------------------------------------


class TestPdfAssetPaths:
    """pdf_asset_paths() maps each fetched PDF asset's source URL to its local path."""

    def test_fetched_pdf_maps_source_url_to_path(self, tmp_path: Path) -> None:
        """A fetched PDF contributes a source-URL → local-path entry."""
        vertex = _pdf("pdfuid001")
        tree = VertexTree(tree_vertices=[vertex])
        ref = _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")
        assert pdf_asset_paths(tree, {"pdfuid001": ref}) == {str(vertex.storage.location): ref.path}

    def test_unfetched_pdf_is_skipped(self, tmp_path: Path) -> None:
        """A PDF vertex with no fetched asset contributes no entry."""
        tree = VertexTree(tree_vertices=[_pdf("pdfuid001")])
        assert pdf_asset_paths(tree, {}) == {}


# ---------------------------------------------------------------------------
# TestApplyPdfEmbeds
# ---------------------------------------------------------------------------


@pytest.mark.pandoc
class TestApplyPdfEmbeds:
    """_apply_pdf_embeds() rewrites stamped PDF-embed link paragraphs into their Typst form."""

    @staticmethod
    def _doc_and_paths(tmp_path: Path, inline: bool, render: str | None = None) -> tuple[pf.Doc, dict[str, Path], str]:
        page = PageVertex(uid="page00001", title="Doc", children=["pdfuid001"])
        vertex = _pdf("pdfuid001", inline=inline)
        if render is not None:
            vertex = PdfVertex(
                uid="pdfuid001",
                storage=asset_storage(_URL_A),
                file_name="dummy.pdf",
                attribute_assignments=[_render_tag(render)],
            )
        tree = VertexTree(tree_vertices=[page, vertex])
        paths = pdf_asset_paths(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        return doc, paths, str(vertex.storage.location)

    def test_name_only_drops_link_keeping_filename_text(self, tmp_path: Path) -> None:
        """A NAME_ONLY occurrence is replaced by bare filename text — no attachment, no hyperlink.

        The reference-placed embed follows its parent's BULLET layout, so the paragraph lives
        inside the bulleted list item.
        """
        doc, paths, _url = self._doc_and_paths(tmp_path, inline=False, render="name-only")
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        item_blocks = list(list(blocks[0].content)[0].content)
        assert len(item_blocks) == 1
        assert isinstance(item_blocks[0], pf.Para)
        assert not any(isinstance(inline, pf.Link) for inline in item_blocks[0].content)
        assert pf.stringify(item_blocks[0]).strip() == "dummy.pdf"
        assert not any(isinstance(block, pf.RawBlock) for block in doc.content)

    def test_strip_removes_the_occurrence_and_its_emptied_container(self, tmp_path: Path) -> None:
        """A STRIP occurrence vanishes entirely — no name, link, pages, or leftover empty bullet."""
        doc, paths, _url = self._doc_and_paths(tmp_path, inline=False, render="strip")
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)
        assert list(doc.content) == []

    def test_inline_mode_renders_pages_without_attachment(self, tmp_path: Path) -> None:
        """An INLINE occurrence is replaced by one image call per page and no attachment."""
        doc, paths, _url = self._doc_and_paths(tmp_path, inline=True)
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.RawBlock)
        assert blocks[0].format == "typst"
        assert "#pdf.attach" not in blocks[0].text
        assert blocks[0].text.count("#image(") == 1
        assert "page: 1" in blocks[0].text
        assert "width: 100%" in blocks[0].text

    def test_link_placement_never_parses_the_pdf(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A LINK-placed occurrence never opens the PDF for a page count — the parse is INLINE's cost alone."""

        def _boom(path: str) -> None:
            raise AssertionError(f"PdfReader must not be invoked for a NAME_ONLY placement (got {path!r})")

        monkeypatch.setattr("guffin.render.pdf_rendering.PdfReader", _boom)
        doc, paths, _url = self._doc_and_paths(tmp_path, inline=False, render="name-only")
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)

    def test_per_site_placements_apply_independently(self, tmp_path: Path) -> None:
        """Two references to one PDF render per their own site tags — one inline, one as bare text."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01", "refsite02"])
        vertex = _pdf("pdfuid001")
        tree = VertexTree(
            tree_vertices=[
                page,
                _reference_site("pdfuid001", render="inline-native", uid="refsite01"),
                _reference_site("pdfuid001", render="name-only", uid="refsite02"),
            ],
            ref_vertices=[vertex],
        )
        paths = pdf_asset_paths(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)
        raw_blocks = [b for b in doc.content if isinstance(b, pf.RawBlock)]
        assert len(raw_blocks) == 1
        assert raw_blocks[0].text.count("#image(") == 1
        # The name-only reference lists with its siblings, so its bare filename
        # paragraph lives inside a list item — collect paragraphs by walking, not just top level.
        bare_paras: list[pf.Para] = []

        def _collect(elem: pf.Element, doc: pf.Doc) -> None:
            if isinstance(elem, pf.Para) and not any(isinstance(i, pf.Link) for i in elem.content):
                bare_paras.append(elem)
            return None

        doc.walk(_collect)
        assert len(bare_paras) == 1
        assert pf.stringify(bare_paras[0]).strip() == "dummy.pdf"

    def test_unfetched_stamped_link_keeps_link_without_scaffold(self, tmp_path: Path) -> None:
        """A stamped paragraph whose PDF was never fetched keeps its link, minus the scaffold attribute."""
        doc, _paths, _url = self._doc_and_paths(tmp_path, inline=False)
        _apply_pdf_embeds(doc, {}, ProjectType.ARTICLE)
        links: list[pf.Link] = []

        def _collect(elem: pf.Element, doc: pf.Doc) -> None:
            if isinstance(elem, pf.Link):
                links.append(elem)
            return None

        doc.walk(_collect)
        assert len(links) == 1
        assert PDF_PLACEMENT_ATTRIBUTE not in links[0].attributes

    def test_prose_paragraph_with_link_untouched(self, tmp_path: Path) -> None:
        """A link inside surrounding prose is not a PDF embed and is left alone."""
        page = PageVertex(uid="page00001", title="Doc", children=["textuid01"])
        text = TextVertex(uid="textuid01", text=f"see [dummy.pdf]({_URL_A}) here")
        tree = VertexTree(tree_vertices=[page, text])
        pdf = _pdf("pdfuid001")
        paths = pdf_asset_paths(
            VertexTree(tree_vertices=[pdf]), {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")}
        )
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        _apply_pdf_embeds(doc, paths, ProjectType.ARTICLE)
        assert not any(isinstance(b, pf.RawBlock) for b in doc.content)

    def test_article3_fixture_occurrences_place_independently(self) -> None:
        """The [[Test Article]] 3 fixture's three displays of one uploaded PDF each stamp per occurrence.

        The same Firebase Storage asset is displayed three times, exercising every resolution path:
        two untagged occurrences — a direct embed in Feature Content and a standalone reference
        to the [[Test Article]] 1 PDF block — which the format-neutral build leaves unset for the
        format pass to default, and one standalone reference tagged ``pdf-render: inline-native``
        at the site.  One PDF, placed per occurrence.
        """
        tree = transcribe(article3_node_tree())
        pdf_url = str(tree.uid_map["pTvGGeTlB"].storage.location)
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        stamps: list[str] = []

        def _collect(elem: pf.Element, doc: pf.Doc) -> None:
            if isinstance(elem, pf.Link) and elem.url == pdf_url and PDF_PLACEMENT_ATTRIBUTE in elem.attributes:
                stamps.append(elem.attributes[PDF_PLACEMENT_ATTRIBUTE])
            return None

        doc.walk(_collect)
        assert sorted(stamps) == ["inline-native", PDF_PLACEMENT_UNSET, PDF_PLACEMENT_UNSET]


class TestAppendixPlacement:
    """_apply_pdf_embeds() moves APPENDIX_NATIVE pages to a generated back-matter appendix."""

    @staticmethod
    def _doc_and_paths(tmp_path: Path, uids: list[str]) -> tuple[pf.Doc, dict[str, Path]]:
        """A page whose children are appendix-tagged embeds of one shared PDF asset."""
        page = PageVertex(uid="page00001", title="Doc", children=uids)
        pdfs = [
            PdfVertex(
                uid=uid,
                storage=asset_storage(_URL_A),
                file_name="dummy.pdf",
                attribute_assignments=[_render_tag("appendix-native")],
            )
            for uid in uids
        ]
        tree = VertexTree(tree_vertices=[page, *pdfs])
        refs = {uid: _dummy_ref(uid, tmp_path, "sha1.pdf") for uid in uids}
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        return doc, pdf_asset_paths(tree, refs)

    def test_anchor_links_into_a_generated_appendix(self, tmp_path: Path) -> None:
        """The embed becomes an internal link, and the pages land under an unnumbered appendix."""
        doc, paths = self._doc_and_paths(tmp_path, ["pdfuid001"])
        _apply_pdf_embeds(doc, paths, ProjectType.BOOK)
        headers = [b for b in doc.content if isinstance(b, pf.Header)]
        assert [h.level for h in headers] == [1, 2]
        assert pf.stringify(headers[0]) == "Appendix"
        assert pf.stringify(headers[1]) == "dummy.pdf"
        # Back matter stands outside the body's numbering, but still reaches the Typst outline.
        assert all("unnumbered" in h.classes for h in headers)
        links: list[pf.Link] = []
        doc.walk(lambda e, d: links.append(e) if isinstance(e, pf.Link) else None)
        assert [link.url for link in links] == [f"#{headers[1].identifier}"]
        raw = next(b for b in doc.content if isinstance(b, pf.RawBlock))
        assert "#image(" in raw.text
        # The first page fits the space left under the heading, so it starts on the heading's own
        # page rather than being pushed to the next one; later pages take a full page each.
        first, *rest = raw.text.splitlines()
        assert "height: 85%" in first and 'fit: "contain"' in first
        # Only the first page is capped; the rest take a page each at full width.
        assert all("height:" not in line for line in rest)

    def test_repeated_occurrences_share_one_appendix_entry(self, tmp_path: Path) -> None:
        """Two embeds of one PDF produce a single subsection that both anchors link to."""
        doc, paths = self._doc_and_paths(tmp_path, ["pdfuid001", "pdfuid002"])
        _apply_pdf_embeds(doc, paths, ProjectType.BOOK)
        headers = [b for b in doc.content if isinstance(b, pf.Header)]
        assert [h.level for h in headers] == [1, 2]
        links: list[pf.Link] = []
        doc.walk(lambda e, d: links.append(e) if isinstance(e, pf.Link) else None)
        assert len(links) == 2
        assert {link.url for link in links} == {f"#{headers[1].identifier}"}
        assert sum(isinstance(b, pf.RawBlock) for b in doc.content) == 1


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

    def test_note_refs_are_underlined_by_default(self) -> None:
        """By default nothing is passed, and the template underlines each note's lead-in."""
        assert not any("note-ref-underline" in arg for arg in self._args(None))

    def test_no_note_ref_underline_variable_passed(self) -> None:
        """Turning the underline off, as for print, passes -V no-note-ref-underline=true."""
        args = _typst_template_args(
            bundled_dir=Path("/bundled"),
            template_path=Path("/bundled/bergfink.typst"),
            template_dir=None,
            number_sections=False,
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=False,
            emit_toc=False,
            provenance=None,
            revision=None,
            revision_name=None,
            cover_image=None,
            note_ref_underline=False,
        )
        assert args[args.index("no-note-ref-underline=true") - 1] == "-V"


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
class TestTypstBulletFilter:
    """typst_bullet.lua rebuilds a classified BulletList as a glyph-column Typst grid."""

    @staticmethod
    def _typst_for(views: ViewMap) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["plain0001", "classed01"])
        plain = TextVertex(uid="plain0001", text="a plain sibling")
        classed = TextVertex(uid="classed01", text="the result block")
        tree = VertexTree(tree_vertices=[page, plain, classed])
        doc, _ = vertex_tree_to_pandoc(tree, {}, views)
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_bullet.lua'}"],
        )

    def test_classified_list_becomes_a_glyph_grid(self) -> None:
        """A semantic item's list is rebuilt as a grid: its boosted glyph in column one, default bullet for siblings."""
        typst = self._typst_for({"classed01": VertexView(semantic=Semantic.RESULT)})
        assert "#grid(" in typst
        assert 'text(size: 1.2em, "⇒"), [' in typst
        assert '"•", [' in typst
        assert "the result block" in typst
        assert "data-guffin" not in typst

    def test_unclassified_list_keeps_native_markers(self) -> None:
        """A list with no classified item passes through as native Typst bullets."""
        typst = self._typst_for({})
        assert "#grid(" not in typst
        assert "- a plain sibling" in typst

    def test_lone_badge_stands_in_the_marker_column(self) -> None:
        """A source channel with no semantic puts its badge where the marker was, like a semantic glyph."""
        typst = self._typst_for({"classed01": VertexView(source_channel=SourceChannel.EMAIL)})
        assert "#grid(" in typst
        assert 'text(size: 1.2em, "📨"), [' in typst
        assert '"•", [' in typst
        # The badge holds the marker, so it no longer leads the item's own text.
        assert "📨 the result block" not in typst

    def test_classified_item_children_render_once(self) -> None:
        """A classified item's nested children serialize into its grid cell exactly once.

        Regression: glyph_and_body once aliased the scaffold Div's content (pandoc.List of an
        existing list returns the same table), so the detection pass appended the children into
        the document and the build pass appended them again — duplicating every child of a
        list's first classified item.
        """
        page = PageVertex(uid="page00001", title="Doc", children=["classed01"])
        classed = TextVertex(uid="classed01", text="the classified block", children=["childuid1"])
        child = TextVertex(uid="childuid1", text="a nested child")
        tree = VertexTree(tree_vertices=[page, classed, child])
        doc, _ = vertex_tree_to_pandoc(tree, {}, {"classed01": VertexView(semantic=Semantic.WARNING)})
        typst = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_bullet.lua'}"],
        )
        assert "#grid(" in typst
        assert typst.count("a nested child") == 1


@pytest.mark.pandoc
class TestTypstAlternativesFilters:
    """typst_alternatives.lua and typst_bullet.lua render alternatives groups per their placement.

    A group in the body's own flow hangs its rail and markers into the margin; a group nested in
    another container sits inside the text column; a bullet-list item's group takes the item's
    marker slot, its list rebuilt as a grid.  The filters run in their production order.
    """

    _ALTERNATIVES: tuple[Alternative, ...] = (
        Alternative(uid="altuid001", text="the *first* other wording"),
        Alternative(uid="altuid002", text="the second other wording"),
    )

    @classmethod
    def _typst_for(cls, page_layout: ChildrenLayout | None) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["plain0001", "versed001", "plain0002"])
        tree = VertexTree(
            tree_vertices=[
                page,
                TextVertex(uid="plain0001", text="before the group"),
                TextVertex(uid="versed001", text="the selected wording", alternatives=cls._ALTERNATIVES),
                TextVertex(uid="plain0002", text="after the group"),
            ]
        )
        views: ViewMap = {} if page_layout is None else {"page00001": VertexView(children_layout=page_layout)}
        doc, _ = vertex_tree_to_pandoc(tree, {}, views)
        resources = _typst_resources_dir()
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[
                f"--lua-filter={resources / 'typst_alternatives.lua'}",
                f"--lua-filter={resources / 'typst_bullet.lua'}",
            ],
        )

    def test_group_in_flow_hangs_into_the_margin(self) -> None:
        """A top-level group calls the template helper with hang on, selected wording first."""
        typst = self._typst_for(ChildrenLayout.DOCUMENT)
        assert "#alternatives-group(hang: true, gutter: alternative-gutter, [" in typst
        assert typst.index("the selected wording") < typst.index("first") < typst.index("the second other wording")
        assert typst.count("], [") == 2
        # The wordings stay native content, so their markup is Typst emphasis, not literal asterisks.
        assert "#emph[first]" in typst

    def test_group_in_a_numbered_list_sits_inside_the_column(self) -> None:
        """A group nested in a numbered item keeps the number as its marker and does not hang."""
        typst = self._typst_for(ChildrenLayout.NUMBERED)
        assert "#alternatives-group(hang: false, gutter: alternative-gutter, [" in typst
        assert "hang: true" not in typst

    def test_group_in_a_bullet_list_takes_the_marker_slot(self) -> None:
        """A bullet item's group becomes radio-marked grid rows under a rail; siblings keep the bullet."""
        typst = self._typst_for(None)
        assert "#alternatives-group" not in typst
        assert "columns: (3pt, 3pt, auto, 1fr)" in typst
        assert 'none, none, "•", [before the group' in typst
        assert "none, none, alternative-marker(true), [the selected wording" in typst
        assert typst.count("alternative-marker(false), alternative-wording[") == 2
        # The rail spans exactly the group's three rows (rows 1-3; the siblings are rows 0 and 4).
        assert "grid.vline(x: 1, start: 1, end: 4, stroke: alternative-rail)" in typst
        assert "row-gutter: (0.65em, 0.4em, 0.4em, 0.65em,)" in typst

    def test_scaffold_never_reaches_the_output(self) -> None:
        """No scaffold class survives into the Typst source, whatever the placement."""
        for layout in (ChildrenLayout.DOCUMENT, ChildrenLayout.NUMBERED, None):
            typst = self._typst_for(layout)
            assert "selected-wording" not in typst
            assert 'alternative-wording"' not in typst

    @staticmethod
    def _epigraph_group_typst(page_layout: ChildrenLayout) -> str:
        """A versioned reference to one epigraph, its alternatives references to two others."""

        def reference(uid: str) -> str:
            return f"[> {uid}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"

        epigraphs = [
            QuoteBlockVertex(
                uid=f"epigr000{n}", quote_type=QuoteType.EPIGRAPH, quote=f"Quotation {n}.", attribution=f"Source {n}"
            )
            for n in (1, 2, 3)
        ]
        versed = TextVertex(
            uid="versed001",
            text=reference("epigr0001"),
            alternatives=(
                Alternative(uid="altuid001", text=reference("epigr0002")),
                Alternative(uid="altuid002", text=reference("epigr0003")),
            ),
        )
        page = PageVertex(uid="page00001", title="Doc", children=["versed001"])
        doc, _ = vertex_tree_to_pandoc(
            VertexTree(tree_vertices=[page, versed], ref_vertices=epigraphs),
            {},
            {"page00001": VertexView(children_layout=page_layout)},
        )
        resources = _typst_resources_dir()
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[
                f"--lua-filter={resources / 'typst_alternatives.lua'}",
                f"--lua-filter={resources / 'typst_quote.lua'}",
                f"--lua-filter={resources / 'typst_bullet.lua'}",
            ],
        )

    def test_epigraph_wordings_are_epigraphs_in_a_display_spaced_group(self) -> None:
        """Each wording of a versioned reference to epigraphs is an epigraph call, spaced as display type."""
        typst = self._epigraph_group_typst(ChildrenLayout.DOCUMENT)
        assert typst.startswith("#alternatives-group(hang: true, gutter: alternative-display-gutter, [")
        assert typst.count("#epigraph(quote: [") == 3
        assert typst.index("Quotation 1.") < typst.index("Quotation 2.") < typst.index("Quotation 3.")
        assert typst.count("attribution: [---Source") == 3

    def test_epigraph_group_in_a_bullet_layout_is_flow_not_a_grid_row(self) -> None:
        """A block-level reference leaves its list, so in a bullet layout the group is flow, not a grid row."""
        typst = self._epigraph_group_typst(ChildrenLayout.BULLET)
        assert "#alternatives-group(hang: true, gutter: alternative-display-gutter, [" in typst
        assert "columns: (3pt, 3pt, auto, 1fr)" not in typst


@pytest.mark.pandoc
class TestTypstQuoteFilter:
    """typst_quote.lua: a pull quote calls fancy-quote with its quotation; a block quote's source line follows it."""

    @staticmethod
    def _typst_for(quote: QuoteBlockVertex) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=[quote.uid])
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, quote]), {}, {})
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_quote.lua'}"],
        )

    def test_pull_quote_calls_fancy_quote_with_quotation_only(self) -> None:
        """The fancy-quote helper receives the quotation and no attribution argument."""
        typst = self._typst_for(QuoteBlockVertex(uid="quote0001", quote_type=QuoteType.PULL, quote="Promoted words."))
        assert "#fancy-quote(quote: [" in typst
        assert "Promoted words." in typst
        assert "attribution" not in typst

    def test_block_quote_attribution_follows_left_aligned(self) -> None:
        """A block quotation's em-dash-led source line is its own paragraph after the quotation, not realigned."""
        typst = self._typst_for(
            QuoteBlockVertex(uid="quote0001", quote_type=QuoteType.BLOCK, quote="Quoted words.", attribution="Someone")
        )
        assert "#quote(block: true)" in typst
        # The Typst writer spells the em dash with its markup shorthand, ---.
        assert "Quoted words.\n\n---Someone" in typst
        assert "align(" not in typst
        assert "#block[" not in typst

    def test_epigraph_calls_epigraph_with_quotation_and_attribution(self) -> None:
        """The epigraph helper receives the quotation and the em-dash-led attribution."""
        typst = self._typst_for(
            QuoteBlockVertex(
                uid="epigr0001",
                quote_type=QuoteType.EPIGRAPH,
                quote="The medium is the message.",
                attribution="McLuhan",
            )
        )
        assert typst.startswith("#epigraph(quote: [The medium is the message.")
        assert "attribution: [---McLuhan" in typst
        assert "epub:type" not in typst

    def test_unattributed_epigraph_passes_no_attribution(self) -> None:
        """An epigraph with no attribution calls the helper with its quotation alone."""
        typst = self._typst_for(QuoteBlockVertex(uid="epigr0001", quote_type=QuoteType.EPIGRAPH, quote="Words."))
        assert "#epigraph(quote: [Words." in typst
        assert "attribution" not in typst


@pytest.mark.pandoc
class TestTypstTodoFilter:
    """typst_todo.lua replaces a TODO item's leading checkbox glyph with a drawn Typst box.

    The template's body font (Noto Sans) has no U+2610, so the glyph itself would render as
    tofu; the filter substitutes a font-independent box drawn from Typst primitives.
    """

    @staticmethod
    def _typst_for(todo_state: TodoState, view_map: ViewMap | None = None) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["todo0001a"])
        item = TodoVertex(uid="todo0001a", todo_state=todo_state, text="a short item")
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, item]), {}, view_map or {})
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_todo.lua'}"],
        )

    def test_open_item_draws_an_empty_box(self) -> None:
        """An open item's ☐ becomes a stroked box with no cross, and the glyph itself is gone."""
        typst = self._typst_for(TodoState.TODO)
        assert "#box(baseline: 15%, width: 0.85em, height: 0.85em, stroke: 0.06em)" in typst
        assert "☐" not in typst
        assert "short item" in typst

    def test_done_item_draws_a_crossed_box(self) -> None:
        """A completed item's ☒ becomes a stroked box crossed by two drawn lines."""
        typst = self._typst_for(TodoState.DONE)
        assert "place(line(start: (8%, 8%), end: (92%, 92%)" in typst
        assert "place(line(start: (92%, 8%), end: (8%, 92%)" in typst
        assert "☒" not in typst

    def test_document_layout_paragraph_is_also_covered(self) -> None:
        """Under a DOCUMENT layout the item is a Para, whose leading glyph is likewise replaced."""
        typst = self._typst_for(
            TodoState.TODO, view_map={"page00001": VertexView(children_layout=ChildrenLayout.DOCUMENT)}
        )
        assert "#box(baseline: 15%" in typst
        assert "☐" not in typst

    def test_mid_paragraph_glyph_is_also_drawn(self) -> None:
        """A checkbox glyph amid a paragraph's inlines — a reference's display — is drawn too."""
        doc = pf.Doc(pf.Para(pf.Str("see"), pf.Space(), pf.Str("☒"), pf.Space(), pf.Str("it")))
        typst = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_todo.lua'}"],
        )
        assert "place(line(start: (8%, 8%)" in typst
        assert "☒" not in typst

    def test_plain_text_is_untouched(self) -> None:
        """A text block with no leading glyph passes through the filter unchanged."""
        page = PageVertex(uid="page00001", title="Doc", children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="no checkbox here")
        doc, _ = vertex_tree_to_pandoc(VertexTree(tree_vertices=[page, block]), {}, {})
        typst = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(doc),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_todo.lua'}"],
        )
        assert "#box(baseline: 15%" not in typst
        assert "- no checkbox here" in typst


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


@pytest.mark.pandoc
class TestTypstKeepWithNextFilter:
    """typst_keep_with_next.lua keeps a lead-in paragraph on the page of the image or table it introduces."""

    _STICKY_OPEN = "#block(sticky: true)["

    @staticmethod
    def _typst_for(*blocks: pf.Block) -> str:
        return pypandoc.convert_text(  # type: ignore[no-untyped-call]
            pandoc_to_json(pf.Doc(*blocks)),
            "typst",
            format="json",
            extra_args=[f"--lua-filter={_typst_resources_dir() / 'typst_keep_with_next.lua'}"],
        )

    @staticmethod
    def _image_para() -> pf.Para:
        return pf.Para(pf.Image(url="faces.png", title=""))

    @staticmethod
    def _table() -> pf.Table:
        cell = pf.TableCell(pf.Plain(pf.Str("x")))
        return pf.Table(pf.TableBody(pf.TableRow(cell)), head=pf.TableHead(), foot=pf.TableFoot())

    def test_lead_in_before_image_is_wrapped_in_sticky_block(self) -> None:
        """The paragraph ahead of an image paragraph is wrapped; the image follows the wrapper."""
        lead_in = pf.Para(pf.Str("See"), pf.Space(), pf.Str("the"), pf.Space(), pf.Str("face:"))
        typst = self._typst_for(lead_in, self._image_para())
        assert typst.count(self._STICKY_OPEN) == 1
        assert (
            typst.index(self._STICKY_OPEN) < typst.index("See the face:") < typst.index("]") < typst.index("faces.png")
        )

    def test_lead_in_before_table_is_wrapped_in_sticky_block(self) -> None:
        """A table counts as a figure-like block too."""
        typst = self._typst_for(pf.Para(pf.Str("Compare:")), self._table())
        assert typst.count(self._STICKY_OPEN) == 1
        assert typst.index(self._STICKY_OPEN) < typst.index("Compare:") < typst.index("#table(")

    def test_lead_in_inside_list_item_is_wrapped(self) -> None:
        """A list item's leading text ahead of its image is wrapped inside the item."""
        typst = self._typst_for(pf.BulletList(pf.ListItem(pf.Plain(pf.Str("APL")), self._image_para())))
        assert typst.count(self._STICKY_OPEN) == 1
        assert typst.index("- ") < typst.index(self._STICKY_OPEN) < typst.index("APL") < typst.index("faces.png")

    def test_text_followed_by_text_is_untouched(self) -> None:
        """Two text paragraphs in a row gain no wrapper."""
        typst = self._typst_for(pf.Para(pf.Str("One.")), pf.Para(pf.Str("Two.")))
        assert self._STICKY_OPEN not in typst

    def test_image_followed_by_image_is_untouched(self) -> None:
        """An image is never a lead-in, so a run of images is left free to break."""
        typst = self._typst_for(self._image_para(), self._image_para())
        assert self._STICKY_OPEN not in typst

    def test_trailing_lead_in_item_of_a_list_is_split_off_and_wrapped(self) -> None:
        """A list ending in a text-only item ahead of an image: that item alone goes in the sticky block."""
        items = [pf.ListItem(pf.Plain(pf.Str("Hieroglyphs"))), pf.ListItem(pf.Plain(pf.Str("APL")))]
        typst = self._typst_for(pf.BulletList(*items), self._image_para())
        assert typst.count(self._STICKY_OPEN) == 1
        assert (
            typst.index("- Hieroglyphs")
            < typst.index(self._STICKY_OPEN)
            < typst.index("- APL")
            < typst.index("faces.png")
        )

    def test_single_item_list_before_image_is_wrapped_whole(self) -> None:
        """A one-item list ahead of an image is wrapped as it is."""
        typst = self._typst_for(pf.BulletList(pf.ListItem(pf.Plain(pf.Str("APL")))), self._image_para())
        assert typst.count(self._STICKY_OPEN) == 1
        assert typst.index(self._STICKY_OPEN) < typst.index("- APL") < typst.index("faces.png")

    def test_split_off_ordered_item_keeps_its_number(self) -> None:
        """An ordered list's split-off last item continues the numbering."""
        items = [
            pf.ListItem(pf.Plain(pf.Str("one"))),
            pf.ListItem(pf.Plain(pf.Str("two"))),
            pf.ListItem(pf.Plain(pf.Str("three"))),
        ]
        typst = self._typst_for(pf.OrderedList(*items, start=4), self._image_para())
        assert typst.count(self._STICKY_OPEN) == 1
        assert "start: 6" in typst
        assert typst.index("+ two") < typst.index(self._STICKY_OPEN) < typst.index("start: 6") < typst.index("+ three")

    def test_list_whose_last_item_has_nested_content_is_untouched(self) -> None:
        """A last item carrying more than its text (a sublist) is not a lead-in to what follows the list."""
        last = pf.ListItem(pf.Plain(pf.Str("APL")), pf.BulletList(pf.ListItem(pf.Plain(pf.Str("sub")))))
        typst = self._typst_for(pf.BulletList(last), self._image_para())
        assert self._STICKY_OPEN not in typst

    def test_only_the_paragraph_adjacent_to_the_image_is_wrapped(self) -> None:
        """Of two paragraphs ahead of an image, only the one touching it is wrapped."""
        typst = self._typst_for(pf.Para(pf.Str("First.")), pf.Para(pf.Str("Second.")), self._image_para())
        assert typst.count(self._STICKY_OPEN) == 1
        assert typst.index("First.") < typst.index(self._STICKY_OPEN) < typst.index("Second.")


@pytest.mark.pandoc
@pytest.mark.skipif(shutil.which("typst") is None, reason="requires typst on PATH")
class TestHeadingLinkPdf:
    """A reference to a heading renders as a working internal link in the compiled PDF."""

    @staticmethod
    def _render_doc(tmp_path_factory: pytest.TempPathFactory, heading_links: bool) -> PdfReader:
        """Render a two-chapter book whose first chapter's prose references the second chapter's heading."""
        ref_url = vertex_link_url("head0002b", VertexLinkKind.REFERENCE)
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["head0001a", "head0002b"]),
                HeadingVertex(uid="head0001a", text="First", heading_level=1, children=["prose0001"]),
                TextVertex(uid="prose0001", text=f"As [Second]({ref_url}) explains.", refs=["head0002b"]),
                HeadingVertex(uid="head0002b", text="Second", heading_level=1, children=["prose0002"]),
                TextVertex(uid="prose0002", text="Target body."),
            ]
        )
        out_dir = tmp_path_factory.mktemp("heading-link")
        render(
            RenderBundle(content=tree),
            profile=BookProfile(),
            filename_stem="doc",
            api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
            options=PdfRenderOptions(output_dir=out_dir, heading_links=heading_links),
        )
        return PdfReader(out_dir / "doc.pdf")

    @pytest.fixture(scope="class")
    def pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """The two-chapter book rendered with heading links on (the default)."""
        return self._render_doc(tmp_path_factory, heading_links=True)

    @pytest.fixture(scope="class")
    def unlinked_pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """The two-chapter book rendered with heading links off."""
        return self._render_doc(tmp_path_factory, heading_links=False)

    @staticmethod
    def _page_index_containing(reader: PdfReader, text: str) -> int:
        """Return the index of the last page whose extracted text contains *text*."""
        return max(i for i, page in enumerate(reader.pages) if text in (page.extract_text() or ""))

    def test_heading_anchor_is_a_named_destination_on_the_headings_page(self, pdf: PdfReader) -> None:
        """The heading's identifier becomes a PDF named destination on the page the heading opens."""
        destination = pdf.named_destinations[heading_anchor("head0002b")]
        assert pdf.get_destination_page_number(destination) == self._page_index_containing(pdf, "Target body.")

    def test_prose_page_links_to_the_heading(self, pdf: PdfReader) -> None:
        """The page holding the referencing prose carries a link annotation to the heading's destination."""
        prose_page = pdf.pages[self._page_index_containing(pdf, "As Second explains.")]
        destinations = [annot.get_object().get("/Dest") for annot in prose_page.get("/Annots") or []]
        assert heading_anchor("head0002b") in destinations

    def test_heading_links_off_renders_bare_text(self, unlinked_pdf: PdfReader) -> None:
        """With heading_links=False the prose keeps the heading's text but carries no link to the heading.

        The heading's named destination may still exist (the table of contents links to it), so only
        the prose page's link annotations are checked.
        """
        prose_page = unlinked_pdf.pages[self._page_index_containing(unlinked_pdf, "As Second explains.")]
        destinations = [annot.get_object().get("/Dest") for annot in prose_page.get("/Annots") or []]
        assert heading_anchor("head0002b") not in destinations


@pytest.mark.pandoc
@pytest.mark.skipif(shutil.which("typst") is None, reason="requires typst on PATH")
class TestAlternativesPdf:
    """Alternatives render in the compiled PDF only on explicit request, in flow and in a bullet list."""

    @staticmethod
    def _text(tmp_path_factory: pytest.TempPathFactory, render_alternatives: bool) -> str:
        """Render a page holding one versioned paragraph and one versioned list item; return the PDF's text."""
        alternatives = (Alternative(uid="altuid001", text="another wording"),)
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["versed001", "host00001"]),
                TextVertex(uid="versed001", text="the selected paragraph", alternatives=alternatives),
                TextVertex(uid="host00001", text="A list:", children=["versed002"]),
                TextVertex(uid="versed002", text="the selected item", alternatives=alternatives),
            ]
        )
        views: ViewMap = {
            "page00001": VertexView(children_layout=ChildrenLayout.DOCUMENT),
            "host00001": VertexView(children_layout=ChildrenLayout.BULLET),
        }
        out_dir = tmp_path_factory.mktemp("alternatives")
        render(
            RenderBundle(content=tree, view=views),
            profile=BookProfile(),
            filename_stem="doc",
            api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
            options=PdfRenderOptions(output_dir=out_dir, render_alternatives=render_alternatives),
        )
        return "\n".join(page.extract_text() or "" for page in PdfReader(out_dir / "doc.pdf").pages)

    def test_requested_alternatives_render(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """With render_alternatives each versioned block shows its alternative after its selected wording."""
        text = self._text(tmp_path_factory, render_alternatives=True)
        assert text.count("another wording") == 2
        assert text.index("the selected paragraph") < text.index("another wording")

    def test_default_renders_selected_wordings_only(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """By default only the selected wordings render."""
        text = self._text(tmp_path_factory, render_alternatives=False)
        assert "the selected paragraph" in text
        assert "the selected item" in text
        assert "another wording" not in text

    def test_epigraph_alternatives_compile(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        """A versioned reference to epigraphs compiles, every wording an epigraph with its source, in order."""

        def reference(uid: str) -> str:
            return f"[> {uid}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"

        epigraphs = [
            QuoteBlockVertex(uid=f"epigr000{n}", quote_type=QuoteType.EPIGRAPH, quote=quote, attribution=source)
            for n, quote, source in ((1, "Selected words.", "Dijkstra"), (2, "Other words.", "Perlis"))
        ]
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["versed001"]),
                TextVertex(
                    uid="versed001",
                    text=reference("epigr0001"),
                    alternatives=(Alternative(uid="altuid001", text=reference("epigr0002")),),
                ),
            ],
            ref_vertices=epigraphs,
        )
        out_dir = tmp_path_factory.mktemp("epigraph-alternatives")
        render(
            RenderBundle(content=tree, view={}),
            profile=BookProfile(),
            filename_stem="doc",
            api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
            options=PdfRenderOptions(output_dir=out_dir, render_alternatives=True),
        )
        text = "\n".join(page.extract_text() or "" for page in PdfReader(out_dir / "doc.pdf").pages)
        assert (
            text.index("Selected words.") < text.index("Dijkstra") < text.index("Other words.") < text.index("Perlis")
        )


@pytest.mark.pandoc
@pytest.mark.skipif(shutil.which("typst") is None, reason="requires typst on PATH")
class TestLongListingFloatPdf:
    """A listing float longer than a page breaks across pages, its caption after the last part.

    A Typst figure is unbreakable unless the template says otherwise, so a long listing float would
    overflow its page and pile its last lines onto its caption (seen 2026-10-18 on Test Article 7).
    """

    _LINES: Final[int] = 120

    @pytest.fixture(scope="class")
    def pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """An article whose only content is a listing float of 120 numbered lines."""
        float_tag = AttributeAssignment(
            attribute=AttributeInstance(
                definition=Attribute(name="float", domain=AttributeDomain.GUFFIN),
                link=VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz"),
            ),
            values=(LiteralValue(value="listing"),),
        )
        code = "\n".join(f"line_{index:03d} = {index}" for index in range(1, self._LINES + 1))
        tree = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["wrapl0001"]),
                TextVertex(
                    uid="wrapl0001", text="A long program.", children=["code00001"], attribute_assignments=[float_tag]
                ),
                CodeBlockVertex(uid="code00001", code=code, language="python"),
            ]
        )
        out_dir = tmp_path_factory.mktemp("long-listing")
        render(
            RenderBundle(content=tree),
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
            options=PdfRenderOptions(output_dir=out_dir),
        )
        return PdfReader(out_dir / "doc.pdf")

    @staticmethod
    def _page_of(reader: PdfReader, text: str) -> int:
        return next(index for index, page in enumerate(reader.pages) if text in (page.extract_text() or ""))

    def test_listing_breaks_and_caption_follows_its_last_line(self, pdf: PdfReader) -> None:
        """The listing starts and ends on different pages, and the caption shares the last line's page."""
        first: Final[int] = self._page_of(pdf, "line_001")
        last: Final[int] = self._page_of(pdf, f"line_{self._LINES:03d}")
        caption: Final[int] = self._page_of(pdf, "Listing 1.")
        assert first < last == caption
        text: Final[str] = pdf.pages[caption].extract_text() or ""
        assert text.index(f"line_{self._LINES:03d}") < text.index("Listing 1. A long program.")


@pytest.mark.pandoc
class TestImageWidthCappedPdf:
    """An image wider than the text column is scaled down to the column; a narrower one is left as it is.

    An image keeps the width its source gave it, and Typst never shrinks an image of a set width, so
    a wide one would run into the margins (seen 2026-10-18 on the SCFH draft-2 Figure 1.1).
    """

    _WIDE: Final[str] = "imgwide01"
    _NARROW: Final[str] = "imgnarr01"

    @pytest.fixture(scope="class")
    def pdf(self, tmp_path_factory: pytest.TempPathFactory) -> pdfium.PdfDocument:
        """An article showing a 2000px-wide image, a 100px-wide one, and a paragraph."""
        png: Final[Path] = FIXTURES_IMAGES_DIR / "test_article_2.png"

        def _image(uid: str, width: int) -> ImageVertex:
            return ImageVertex(
                uid=uid,
                storage=asset_storage(f"https://firebasestorage.googleapis.com/v0/b/t/o/{uid}.png"),
                media_type=MediaType.PNG,
                scaled_image_size=ImageSize(width=width),
            )

        tree: Final[VertexTree] = VertexTree(
            tree_vertices=[
                PageVertex(uid="page00001", title="Doc", children=["para00001", self._WIDE, self._NARROW]),
                TextVertex(uid="para00001", text="A paragraph long enough to reach both margins. " * 3),
                _image(self._WIDE, 2000),
                _image(self._NARROW, 100),
            ]
        )
        refs: Final[dict[str, AssetRef]] = {
            uid: AssetRef(uid=uid, path=png, size=ImageSize(width=940, height=1154))
            for uid in (self._WIDE, self._NARROW)
        }
        out_dir: Final[Path] = tmp_path_factory.mktemp("image-width")
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "guffin.render.pdf_rendering.fetch_and_enrich_assets", lambda content, *_args: (content, refs)
            )
            render(
                RenderBundle(content=tree),
                profile=ArticleProfile(),
                filename_stem="doc",
                api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
                options=PdfRenderOptions(output_dir=out_dir),
            )
        return pdfium.PdfDocument(out_dir / "doc.pdf")

    @staticmethod
    def _bounds(pdf: pdfium.PdfDocument, object_type: int) -> list[tuple[float, float, float, float]]:
        return [obj.get_bounds() for page in pdf for obj in page.get_objects(filter=[object_type])]

    def test_wide_image_fills_the_column(self, pdf: pdfium.PdfDocument) -> None:
        """The wide image starts at the text's left margin and ends at the matching right one."""
        text_left: Final[float] = min(left for left, _, _, _ in self._bounds(pdf, pdfium_raw.FPDF_PAGEOBJ_TEXT))
        left, _, right, _ = max(self._bounds(pdf, pdfium_raw.FPDF_PAGEOBJ_IMAGE), key=lambda box: box[2] - box[0])
        assert left == pytest.approx(text_left, abs=2)
        assert right == pytest.approx(pdf[0].get_width() - left, abs=0.5)

    def test_narrow_image_keeps_its_width(self, pdf: pdfium.PdfDocument) -> None:
        """The 100px image is set at its own width, 75pt."""
        widths: Final[list[float]] = [
            right - left for left, _, right, _ in self._bounds(pdf, pdfium_raw.FPDF_PAGEOBJ_IMAGE)
        ]
        assert min(widths) == pytest.approx(75, abs=0.5)
