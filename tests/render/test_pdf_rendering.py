"""Unit tests for guffin.render.pdf_rendering's PDF-embed preparation and Doc rewriting."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.
# pyright: reportPrivateUsage=false
# Rationale: these unit tests deliberately exercise module-private helpers (e.g.
# pdf_asset_paths, _apply_pdf_embeds, _typst_str) directly.

import shutil
from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]
import pytest
from conftest import FIXTURES_PDF_DIR, article3_node_tree

from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.vertex import HeadingVertex, PageVertex, PdfVertex, TextVertex, TodoState, TodoVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, Semantic, SourceChannel, VertexView, ViewMap
from guffin.render.asset_fetch import AssetRef, pdf_asset_paths
from guffin.render.pandoc_ast import pandoc_to_json
from guffin.render.pandoc_rendering import PDF_PLACEMENT_ATTRIBUTE, PDF_PLACEMENT_UNSET, vertex_tree_to_pandoc
from guffin.render.pdf_rendering import (
    _apply_pdf_embeds,
    _prepare_title_metadata,
    _typst_resources_dir,
    _typst_str,
    _typst_template_args,
    pdf_asset_paths,
)
from guffin.render.project import ProjectType, TopLevelDivision
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
    original_file_name: str | None = "dummy.pdf",
    inline: bool = False,
) -> PdfVertex:
    return PdfVertex(
        uid=uid,
        source=url,  # type: ignore[arg-type]
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
# TestPdfAssetPaths
# ---------------------------------------------------------------------------


class TestPdfAssetPaths:
    """pdf_asset_paths() maps each fetched PDF asset's source URL to its local path."""

    def test_fetched_pdf_maps_source_url_to_path(self, tmp_path: Path) -> None:
        """A fetched PDF contributes a source-URL → local-path entry."""
        vertex = _pdf("pdfuid001")
        tree = VertexTree(tree_vertices=[vertex])
        ref = _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")
        assert pdf_asset_paths(tree, {"pdfuid001": ref}) == {str(vertex.source): ref.path}

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
                source=_URL_A,  # type: ignore[arg-type]
                original_file_name="dummy.pdf",
                attribute_assignments=[_render_tag(render)],
            )
        tree = VertexTree(tree_vertices=[page, vertex])
        paths = pdf_asset_paths(tree, {"pdfuid001": _dummy_ref("pdfuid001", tmp_path, "sha1.pdf")})
        doc, _ = vertex_tree_to_pandoc(tree, {}, {})
        return doc, paths, str(vertex.source)

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
        pdf_url = str(tree.uid_map["pTvGGeTlB"].source)
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
                source=_URL_A,  # type: ignore[arg-type]
                original_file_name="dummy.pdf",
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
