"""Unit tests for guffin.render.md_rendering."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_MD_DIR, article1_node_tree

from guffin.common.filenames import shell_safe_filename
from guffin.common.revision import Revision
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source import CodeSource
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import CodeBlockVertex, HeadingVertex, PageVertex, QuoteBlockVertex, QuoteType, TextVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import Semantic, SourceChannel, VertexView
from guffin.render.md_rendering import render
from guffin.render.project import BookProfile, DefaultProfile
from guffin.render.render_options import MarkdownRenderOptions
from guffin.roam.local_api import ApiEndpoint
from guffin.transcribe.roam_tree_to_guffin import build_view_map, transcribe

pytestmark = pytest.mark.pandoc


class TestRenderArticleFixture:
    """Integration tests for the md_rendering Pandoc output path."""

    def test_article_fixture_renders_to_expected_markdown(self, tmp_path: Path) -> None:
        """Rendering article1 to a plain ``.md`` file matches the expected fixture.

        Exercises the full :func:`~guffin.render.md_rendering.render` path with
        ``should_bundle=False`` — the same path used by ``tests/regen_fixtures.py`` to
        produce the expected fixture — so the production resolver and every GFM
        Lua filter are covered.  ``should_bundle=False`` never fetches images, so the
        supplied :class:`~guffin.roam.local_api.ApiEndpoint` is unused.
        """
        # render no longer normalizes; callers pass an already-safe stem.
        stem: Final[str] = shell_safe_filename("[[Test Article]] 1")
        node_tree = article1_node_tree()
        render_bundle: Final[RenderBundle] = RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            render_bundle,
            profile=DefaultProfile(),
            filename_stem=stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        expected: Final[str] = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert result == expected


class TestSemanticBullets:
    """Classified list items render dash + glyph in GFM (via gfm_bullet.lua and badge injection)."""

    def test_classified_items_render_glyphs(self, tmp_path: Path) -> None:
        """A semantic renders its bullet glyph, a source channel its badge, both after the dash."""
        page = PageVertex(uid="page00001", title="P", children=["plain0001", "classed01", "badge0001"])
        plain = TextVertex(uid="plain0001", text="a plain sibling")
        classed = TextVertex(uid="classed01", text="the result block")
        badged = TextVertex(uid="badge0001", text="notes from the call")
        bundle: Final[RenderBundle] = RenderBundle(
            content=VertexTree(tree_vertices=[page, plain, classed, badged]),
            view={
                "classed01": VertexView(semantic=Semantic.RESULT),
                "badge0001": VertexView(source_channel=SourceChannel.VOICE_CALL),
            },
        )
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            bundle,
            profile=DefaultProfile(),
            filename_stem="semantic",
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / "semantic.md").read_text(encoding="utf-8")
        assert "- a plain sibling" in result
        assert "- ⇒ the result block" in result
        assert "- 📞 notes from the call" in result
        assert "data-guffin" not in result


def _book_bundle() -> RenderBundle:
    """A minimal book: a metadata-bearing page root with one chapter heading and one paragraph."""
    link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")

    def _meta(name: str, value: str) -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
            values=(LiteralValue(value=value),),
        )

    page = PageVertex(
        uid="page00001",
        title="Dorian Gray",
        children=["chap00001"],
        attribute_assignments=[_meta("authors", "Oscar Wilde"), _meta("publisher", "Lippincott's Monthly Magazine")],
    )
    chapter = HeadingVertex(uid="chap00001", text="Chapter I", heading_level=1, children=["text00001"])
    text = TextVertex(uid="text00001", text="The studio was filled with the rich odour of roses.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, chapter, text]), view={})


class TestFrontMatter:
    """A title-page-emitting profile serializes document metadata as YAML front matter in GFM."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, profile: BookProfile | DefaultProfile) -> str:
        render(
            _book_bundle(),
            profile=profile,
            filename_stem="book",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "book.md").read_text(encoding="utf-8")

    def test_book_emits_yaml_front_matter(self, tmp_path: Path) -> None:
        """A book render opens with a YAML block carrying the bibliographic metadata."""
        result = self._render(tmp_path, BookProfile())
        assert result.startswith("---\n")
        front_matter = result.split("---", 2)[1]
        assert "author:\n- Oscar Wilde" in front_matter  # MetaList: one YAML list entry per author
        assert "publisher: Lippincott’s Monthly Magazine" in front_matter
        assert "title: Dorian Gray" in front_matter

    def test_book_title_renders_both_in_front_matter_and_h1(self, tmp_path: Path) -> None:
        """The title appears in the YAML block and as the leading H1."""
        result = self._render(tmp_path, BookProfile())
        body = result.split("---", 2)[2]
        assert "# Dorian Gray" in body

    def test_default_profile_emits_no_front_matter(self, tmp_path: Path) -> None:
        """A default (article) render carries no YAML block; the H1 title opens the document."""
        result = self._render(tmp_path, DefaultProfile())
        assert result.startswith("# Dorian Gray")
        assert "publisher:" not in result

    def test_suppress_attributes_keeps_the_bibliographic_metadata(self, tmp_path: Path) -> None:
        """--suppress-attributes hides content-attribute pills but leaves guffin metadata in force."""
        render(
            _book_bundle(),
            profile=BookProfile(),
            filename_stem="book",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False, suppress_attributes=True),
        )
        result = (tmp_path / "book.md").read_text(encoding="utf-8")
        front_matter = result.split("---", 2)[1]
        assert "author:\n- Oscar Wilde" in front_matter
        assert "publisher: Lippincott’s Monthly Magazine" in front_matter


class TestRevisionLine:
    """A non-front-matter profile renders the authored revision name directly below the title H1."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, bundle: RenderBundle, profile: BookProfile | DefaultProfile) -> str:
        render(
            bundle,
            profile=profile,
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_default_profile_renders_revision_below_title(self, tmp_path: Path) -> None:
        """With an authored revision name, an emphasized revision line follows the H1 title."""
        bundle = _book_bundle().with_revision(Revision(snapshot="d8666f090982", revision="draft-3"))
        result = self._render(tmp_path, bundle, DefaultProfile())
        assert result.startswith("# Dorian Gray\n\n*revision: draft-3*\n")

    def test_no_authored_name_no_revision_line(self, tmp_path: Path) -> None:
        """A revision without an authored name inserts nothing."""
        bundle = _book_bundle().with_revision(Revision(snapshot="d8666f090982"))
        result = self._render(tmp_path, bundle, DefaultProfile())
        assert "revision" not in result

    def test_no_revision_no_revision_line(self, tmp_path: Path) -> None:
        """A bundle with no captured revision inserts nothing."""
        result = self._render(tmp_path, _book_bundle(), DefaultProfile())
        assert "revision" not in result

    def test_front_matter_profile_omits_revision_line(self, tmp_path: Path) -> None:
        """A title-page-emitting profile keeps the body free of the revision line."""
        bundle = _book_bundle().with_revision(Revision(snapshot="d8666f090982", revision="draft-3"))
        result = self._render(tmp_path, bundle, BookProfile())
        assert "*revision: draft-3*" not in result

    def test_front_matter_profile_carries_summary_in_metadata(self, tmp_path: Path) -> None:
        """A title-page-emitting profile records the entire revision summary in the YAML block."""
        revision = Revision(
            snapshot="d8666f090982" + "0" * 52,
            revision="draft-3",
            last_edited_at=datetime(2026, 7, 11, 18, 22, tzinfo=UTC),
            fetched_at=datetime(2026, 7, 12, 9, 30, tzinfo=UTC),
        )
        result = self._render(tmp_path, _book_bundle().with_revision(revision), BookProfile())
        front_matter = result.split("---", 2)[1]
        assert revision.summary() in front_matter

    def test_default_profile_carries_no_revision_metadata(self, tmp_path: Path) -> None:
        """A profile without front matter serializes no revision metadata entry."""
        bundle = _book_bundle().with_revision(Revision(snapshot="d8666f090982", revision="draft-3"))
        result = self._render(tmp_path, bundle, DefaultProfile())
        assert "snapshot: d8666f090982" not in result


class TestBracketEntities:
    """Literal square brackets render as HTML character entities, never as backslash escapes."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def test_literal_brackets_become_entities(self, tmp_path: Path) -> None:
        r"""Bare bracketed text emits &#91;/&#93; — Typora's MathJax misreads \[…\] as display math."""
        page = PageVertex(uid="page00001", title="Doc", children=["text00001"])
        text = TextVertex(uid="text00001", text="This \\[para\\] features \\[*italics*\\]")
        bundle = RenderBundle(content=VertexTree(tree_vertices=[page, text]), view={})
        render(
            bundle,
            profile=DefaultProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result = (tmp_path / "doc.md").read_text(encoding="utf-8")
        assert "&#91;para&#93;" in result
        assert "&#91;*italics*&#93;" in result
        assert "\\[" not in result


class TestPullQuoteRendering:
    """A pull quote ([[!QUOTE]]) renders best-effort GFM: bold ❝-led quote, italic attribution."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, vtx: QuoteBlockVertex) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["quote0001"])
        bundle = RenderBundle(content=VertexTree(tree_vertices=[page, vtx]), view={})
        render(
            bundle,
            profile=DefaultProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_pull_quote_bolds_quotation_with_leading_glyph(self, tmp_path: Path) -> None:
        """The quotation renders as a bold block-quote line led by the ❝ (U+275D) ornament."""
        vtx = QuoteBlockVertex(
            uid="quote0001",
            quote_type=QuoteType.PULL,
            quote="In the long run every program becomes rococo.",
            attribution="— Alan Perlis",
        )
        result = self._render(tmp_path, vtx)
        assert "> **❝ In the long run every program becomes rococo.**" in result

    def test_pull_quote_italicizes_attribution(self, tmp_path: Path) -> None:
        """The attribution renders as an italic block-quote line."""
        vtx = QuoteBlockVertex(
            uid="quote0001", quote_type=QuoteType.PULL, quote="The quotation.", attribution="The attribution."
        )
        result = self._render(tmp_path, vtx)
        assert "> *The attribution.*" in result

    def test_block_quote_is_unchanged(self, tmp_path: Path) -> None:
        """A plain BLOCK quote gets no glyph, bold, or forced italic."""
        vtx = QuoteBlockVertex(uid="quote0001", quote_type=QuoteType.BLOCK, quote="Just a plain quote.")
        result = self._render(tmp_path, vtx)
        assert "> Just a plain quote." in result
        assert "❝" not in result


class TestHeadingDemotion:
    """With a title H1 emitted, content headings demote one level so the title contains them."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render_bundle(self, tmp_path: Path, bundle: RenderBundle) -> str:
        render(
            bundle,
            profile=DefaultProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_titled_document_demotes_content_headings(self, tmp_path: Path) -> None:
        """A page root's level-1 chapter renders as H2 under the H1 title."""
        result = self._render_bundle(tmp_path, _book_bundle())
        assert "\n## Chapter I\n" in result
        assert "\n# Chapter I\n" not in result

    def test_title_h1_itself_is_not_demoted(self, tmp_path: Path) -> None:
        """The leading title H1 stays H1."""
        result = self._render_bundle(tmp_path, _book_bundle())
        assert result.startswith("# Dorian Gray\n")

    def test_heading_root_titles_the_document_and_demotes_content(self, tmp_path: Path) -> None:
        """A heading-rooted subtree titles the document from its root, demoting content headings."""
        root = HeadingVertex(uid="root00001", text="Notes", heading_level=1, children=["chap00001"])
        chapter = HeadingVertex(uid="chap00001", text="Chapter I", heading_level=1, children=["text00001"])
        text = TextVertex(uid="text00001", text="Some prose.")
        bundle = RenderBundle(content=VertexTree(tree_vertices=[root, chapter, text]), view={})
        result = self._render_bundle(tmp_path, bundle)
        # The root heading "Notes" becomes the title H1; the content "Chapter I" is demoted to H2.
        assert result.startswith("# Notes\n")
        assert "\n## Chapter I\n" in result


def _numbered_bundle() -> RenderBundle:
    """A page with one element-numbered chapter heading and one paragraph."""
    page = PageVertex(uid="page00001", title="Numbered Doc", children=["chap00001"])
    chapter = HeadingVertex(uid="chap00001", text="[1.1] Chapter I", heading_level=1, children=["text00001"])
    text = TextVertex(uid="text00001", text="Body text.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, chapter, text]), view={})


class TestElementNumberRendering:
    """Internal element numbers render only on explicit request."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, emit_element_numbers: bool) -> str:
        render(
            _numbered_bundle(),
            profile=DefaultProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(
                output_dir=tmp_path, should_bundle=False, emit_element_numbers=emit_element_numbers
            ),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_default_strips_element_numbers(self, tmp_path: Path) -> None:
        """By default a heading's marker is absent from the output."""
        result = self._render(tmp_path, emit_element_numbers=False)
        assert "Chapter I" in result
        assert "1.1" not in result

    def test_emit_option_keeps_element_numbers(self, tmp_path: Path) -> None:
        """With emit_element_numbers the marker renders (brackets entity-encoded for Typora)."""
        result = self._render(tmp_path, emit_element_numbers=True)
        assert "&#91;1.1&#93; Chapter I" in result


def _sourced_bundle() -> RenderBundle:
    """A page with one sourced Python code block."""
    page = PageVertex(uid="page00001", title="Sourced Doc", children=["code00001"])
    code = CodeBlockVertex(
        uid="code00001",
        code="print(1)",
        language="python",
        code_source=CodeSource(
            url="https://github.com/psf/requests/blob/main/src/requests/api.py#L14-L60",
            commit_sha="0d9ca427f7d7dbe92694284d4a6249178255036e",
            fetched_date="2026-07-17",
        ),
    )
    return RenderBundle(content=VertexTree(tree_vertices=[page, code]), view={})


class TestCodeSourceRendering:
    """Code-source attributions render only on explicit request."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, emit_code_sources: bool) -> str:
        render(
            _sourced_bundle(),
            profile=DefaultProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(
                output_dir=tmp_path, should_bundle=False, emit_code_sources=emit_code_sources
            ),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_default_omits_attribution(self, tmp_path: Path) -> None:
        """By default a sourced code block renders with no attribution line."""
        result = self._render(tmp_path, emit_code_sources=False)
        assert "print(1)" in result
        assert "Source:" not in result

    def test_emit_option_renders_attribution(self, tmp_path: Path) -> None:
        """With emit_code_sources the italic attribution line follows the listing, SHA-pinned link included."""
        result = self._render(tmp_path, emit_code_sources=True)
        assert "print(1)" in result
        assert "Source:" in result
        assert "https://github.com/psf/requests/blob/0d9ca427f7d7dbe92694284d4a6249178255036e/" in result
        assert "<div" not in result


def _parts_book_bundle() -> RenderBundle:
    """A parts book: one part (with a chapter) followed by a root-level back-matter section."""
    link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="metapage1")

    def _meta(name: str, value: str) -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=link),
            values=(LiteralValue(value=value),),
        )

    page = PageVertex(uid="page00001", title="Travels", children=["part00001", "sect00001"])
    part = HeadingVertex(
        uid="part00001",
        text="Book IV",
        heading_level=1,
        children=["chap00001"],
        attribute_assignments=[_meta("element-type", "part")],
    )
    chapter = HeadingVertex(uid="chap00001", text="Chapter 1", heading_level=2, children=["text00001"])
    text = TextVertex(uid="text00001", text="Wars among the Tartar princes.")
    section = HeadingVertex(
        uid="sect00001",
        text="About the Author",
        heading_level=2,
        children=["text00002"],
        attribute_assignments=[_meta("matter", "back-matter")],
    )
    bio = TextVertex(uid="text00002", text="Rustichello da Pisa.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, part, chapter, text, section, bio]), view={})


class TestPartsBookSectionPromotion:
    """A parts book renders root-level non-body sections at part level, not chapter level."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, profile: BookProfile | DefaultProfile) -> str:
        render(
            _parts_book_bundle(),
            profile=profile,
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_parts_book_promotes_back_matter_section_to_part_level(self, tmp_path: Path) -> None:
        """In a parts book the back-matter section renders at the parts' own heading level."""
        result = self._render(tmp_path, BookProfile(with_parts=True))
        assert "## Book IV" in result
        assert "## About the Author" in result
        assert "### About the Author" not in result

    def test_default_profile_keeps_the_authored_level(self, tmp_path: Path) -> None:
        """Outside a parts book the section keeps its authored (chapter) level."""
        result = self._render(tmp_path, DefaultProfile())
        assert "### About the Author" in result
