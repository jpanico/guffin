"""Unit tests for guffin.render.md_rendering."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
import regex
from conftest import FIXTURES_MD_DIR, article1_node_tree

from guffin.common.filenames import shell_safe_filename
from guffin.common.revision import Revision
from guffin.model.alternative import Alternative
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source import CodeSource
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import (
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    NotesVertex,
    PageVertex,
    QuoteBlockVertex,
    QuoteType,
    TextVertex,
    TodoState,
    TodoVertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.model.vertex_view import ChildrenLayout, Semantic, SourceChannel, VertexView
from guffin.render.asset_fetch import AssetRef
from guffin.render.md_rendering import _remove_stripped_bundle_assets, render
from guffin.render.project import ArticleProfile, BookProfile, ProjectProfile
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
            profile=ArticleProfile(),
            filename_stem=stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        expected: Final[str] = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert result == expected

    def test_image_child_block_follows_the_image_as_its_caption(self, tmp_path: Path) -> None:
        """Article 1's resized image (illustration 2.1) has one child block, which renders as a caption.

        The child's text follows the image as the next paragraph — in a plain ``.md`` export the
        image is the link to its hosted file, since nothing is fetched — and is the one caption in
        the article, so a regression in the children-as-caption rendering shows here by name rather
        than only as a byte difference against the recorded fixture.
        """
        stem: Final[str] = shell_safe_filename("[[Test Article]] 1")
        node_tree = article1_node_tree()
        render_bundle: Final[RenderBundle] = RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            render_bundle,
            profile=ArticleProfile(),
            filename_stem=stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        caption: Final[str] = "A caption authored as the image\u2019s child block."
        assert result.count(caption) == 1
        assert regex.search(
            r"^\[aOC1FnrcwK\.jpeg\.enc\]\([^)]+\)\n\n" + regex.escape(caption) + r"\n", result, regex.MULTILINE
        )

    def test_listing_caption_precedes_its_source_attribution(self, tmp_path: Path) -> None:
        """Article 1's three listings (Section 1.2) render caption and attribution in the authored combinations.

        Listing 1.2.1 has a caption child and no ``code-source::`` tag, 1.2.2 a tag and no caption,
        1.2.3 both.  With code sources emitted, a caption follows its fence as the next paragraph
        and precedes the attribution; a listing without a caption goes straight to its attribution;
        a listing without a tag gets no attribution.
        """
        stem: Final[str] = shell_safe_filename("[[Test Article]] 1")
        node_tree = article1_node_tree()
        render_bundle: Final[RenderBundle] = RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            render_bundle,
            profile=ArticleProfile(),
            filename_stem=stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False, emit_code_sources=True),
        )
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        listing_1: Final[str] = result[result.index("#### listing 1.2.1") : result.index("#### listing 1.2.2")]
        listing_2: Final[str] = result[result.index("#### listing 1.2.2") : result.index("#### listing 1.2.3")]
        listing_3: Final[str] = result[result.index("#### listing 1.2.3") : result.index("## Section 2")]
        caption: Final[str] = "A caption authored as the listing\u2019s child block"
        assert "\n```\n\n" + caption + ".\n" in listing_1
        assert "Source:" not in listing_1
        assert "\n```\n\n*Source: [jpanico/guffin/src/guffin/common/json_value.py]" in listing_2
        assert caption not in listing_2
        assert (
            "\n```\n\n" + caption + ", set above its source attribution.\n\n"
            "*Source: [jpanico/guffin/src/guffin/common/geometry.py L1\u2013L8]"
        ) in listing_3

    def test_figure_float_renders_anchor_image_and_labelled_caption(self, tmp_path: Path) -> None:
        """Article 1's figure float (Section 1.3) renders unwrapped: anchor, image, then the labelled caption.

        The wrapper is a text block tagged ``float:: figure`` whose one content child is the image
        block itself; in a plain ``.md`` export the image is the link to its hosted file.  The
        article numbers its floats sequentially, so the caption is led by *Figure 1.* in bold, the
        whole line emphasized, after the ``float-<uid>`` anchor the reference lands on: the text block
        before it refers to the float with the kind-word alias ``[figure](((uid)))``, which renders
        as a Markdown link to that anchor, the word completed with the number.
        """
        stem: Final[str] = shell_safe_filename("[[Test Article]] 1")
        node_tree = article1_node_tree()
        render_bundle: Final[RenderBundle] = RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            render_bundle,
            profile=ArticleProfile(),
            filename_stem=stem,
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        section: Final[str] = result[result.index("### Section 1.3") : result.index("## Section 2")]
        assert "<figure" not in section
        assert "see [figure 1](#float-hJFB2787-) \u2013 which" in section
        assert regex.search(
            r'^<a id="float-hJFB2787-"></a>\n\n\[A flower\]\([^)]+\)\n\n'
            r"\*\*\*Figure 1\.\*\* The flower, as a numbered figure\.\*\n",
            section,
            regex.MULTILINE,
        )


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
            profile=ArticleProfile(),
            filename_stem="semantic",
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / "semantic.md").read_text(encoding="utf-8")
        assert "- a plain sibling" in result
        assert "- ⇒ the result block" in result
        assert "- 📞 notes from the call" in result
        assert "data-guffin" not in result


class TestTodoRendering:
    """TODO items and references to them render checkboxes in GFM."""

    def test_items_and_inline_refs_render_checkboxes(self, tmp_path: Path) -> None:
        """An item renders native task-list syntax; an inline ref carries a size-boosted glyph span."""
        ref_url: Final[str] = vertex_link_url("tododone1", VertexLinkKind.REFERENCE)
        page = PageVertex(uid="page00001", title="P", children=["todoopen1", "tododone1", "reftxt001"])
        open_item = TodoVertex(uid="todoopen1", todo_state=TodoState.TODO, text="an open item")
        done_item = TodoVertex(uid="tododone1", todo_state=TodoState.DONE, text="a completed item")
        ref = TextVertex(uid="reftxt001", text=f"see [a completed item]({ref_url}) inline")
        bundle: Final[RenderBundle] = RenderBundle(
            content=VertexTree(tree_vertices=[page, open_item, done_item, ref]), view={}
        )
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(
            bundle,
            profile=ArticleProfile(),
            filename_stem="todos",
            api_endpoint=endpoint,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result: Final[str] = (tmp_path / "todos.md").read_text(encoding="utf-8")
        assert "- [ ] an open item" in result
        assert "- [x] a completed item" in result
        # The inline reference's glyph is boosted 20% by gfm_todo.lua and its DONE state is
        # displayed with the checkmark form (☑), matching GFM's native checkboxes; the leading
        # task-list checkboxes above stay bare so the GFM writer's native syntax wins.
        assert 'see <span style="font-size: 1.2em; line-height: 1">☑</span> a completed item inline' in result


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

    def _render(self, tmp_path: Path, profile: BookProfile | ArticleProfile) -> str:
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
        result = self._render(tmp_path, ArticleProfile())
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

    def _render(self, tmp_path: Path, bundle: RenderBundle, profile: BookProfile | ArticleProfile) -> str:
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
        result = self._render(tmp_path, bundle, ArticleProfile())
        assert result.startswith("# Dorian Gray\n\n*revision: draft-3*\n")

    def test_no_authored_name_no_revision_line(self, tmp_path: Path) -> None:
        """A revision without an authored name inserts nothing."""
        bundle = _book_bundle().with_revision(Revision(snapshot="d8666f090982"))
        result = self._render(tmp_path, bundle, ArticleProfile())
        assert "revision" not in result

    def test_no_revision_no_revision_line(self, tmp_path: Path) -> None:
        """A bundle with no captured revision inserts nothing."""
        result = self._render(tmp_path, _book_bundle(), ArticleProfile())
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
        result = self._render(tmp_path, bundle, ArticleProfile())
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
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        result = (tmp_path / "doc.md").read_text(encoding="utf-8")
        assert "&#91;para&#93;" in result
        assert "&#91;*italics*&#93;" in result
        assert "\\[" not in result


class TestPullQuoteRendering:
    """A pull quote renders best-effort GFM (a bold ❝-led quotation); a block quote ends with its source line."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, vtx: QuoteBlockVertex) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["quote0001"])
        bundle = RenderBundle(content=VertexTree(tree_vertices=[page, vtx]), view={})
        render(
            bundle,
            profile=ArticleProfile(),
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
        )
        result = self._render(tmp_path, vtx)
        assert "> **❝ In the long run every program becomes rococo.**" in result

    def test_pull_quote_keeps_every_paragraph(self, tmp_path: Path) -> None:
        """Every paragraph of a pull quote is bold quotation; only the first is led by the ornament."""
        vtx = QuoteBlockVertex(
            uid="quote0001", quote_type=QuoteType.PULL, quote="First paragraph.\n\nSecond paragraph."
        )
        result = self._render(tmp_path, vtx)
        assert "> **❝ First paragraph.**" in result
        assert "> **Second paragraph.**" in result

    def test_block_quote_ends_with_its_source_line(self, tmp_path: Path) -> None:
        """A block quotation's attribution is its last line, led by an em dash, its emphasis intact."""
        vtx = QuoteBlockVertex(
            uid="quote0001",
            quote_type=QuoteType.BLOCK,
            quote="I wish to God these calculations had been executed by steam!",
            attribution="*Charles Babbage*, c. 1821",
        )
        result = self._render(tmp_path, vtx)
        # Pandoc's smart parsing binds the abbreviation "c." to the year with a no-break space.
        assert (
            "> I wish to God these calculations had been executed by steam!\n>\n> —*Charles Babbage*, c. 1821" in result
        )
        assert "<div" not in result

    def test_epigraph_is_an_italic_block_quote_ending_with_its_source_line(self, tmp_path: Path) -> None:
        """An epigraph renders as a block quote: the quotation italic, the em-dash-led source line upright."""
        vtx = QuoteBlockVertex(
            uid="quote0001",
            quote_type=QuoteType.EPIGRAPH,
            quote="The medium is *the* message.",
            attribution="*Understanding Media*",
        )
        result = self._render(tmp_path, vtx)
        assert "> *The medium is the message.*\n>\n> —*Understanding Media*" in result
        assert "<div" not in result

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
            profile=ArticleProfile(),
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
            profile=ArticleProfile(),
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


def _heading_ref_bundle(*, second_title: str = "Second", first_title: str = "First") -> RenderBundle:
    """A page whose first section's prose references the second section's heading."""
    ref_url = vertex_link_url("head0002b", VertexLinkKind.REFERENCE)
    page = PageVertex(uid="page00001", title="Doc", children=["head0001a", "head0002b"])
    first = HeadingVertex(uid="head0001a", text=first_title, heading_level=1, children=["prose0001"])
    prose = TextVertex(uid="prose0001", text=f"As [Second]({ref_url}) explains.", refs=["head0002b"])
    second = HeadingVertex(uid="head0002b", text=second_title, heading_level=1, children=["prose0002"])
    body = TextVertex(uid="prose0002", text="Target body.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, first, prose, second, body]), view={})


class TestHeadingLinkRendering:
    """A reference to a heading links to its GitHub-style slug, or to an HTML anchor when the slug is unusable."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(
        self,
        tmp_path: Path,
        *,
        should_bundle: bool,
        heading_links: bool = True,
        render_bundle: RenderBundle | None = None,
    ) -> str:
        render(
            render_bundle if render_bundle is not None else _heading_ref_bundle(),
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(
                output_dir=tmp_path, should_bundle=should_bundle, heading_links=heading_links
            ),
        )
        md_path = tmp_path / "doc.mdbundle" / "doc.md" if should_bundle else tmp_path / "doc.md"
        return md_path.read_text(encoding="utf-8")

    @pytest.mark.parametrize("should_bundle", [True, False])
    def test_reference_links_to_heading_slug(self, tmp_path: Path, should_bundle: bool) -> None:
        """The prose links to the heading's text-derived slug, and no anchor is emitted."""
        result = self._render(tmp_path, should_bundle=should_bundle)
        assert "As [Second](#second) explains." in result
        assert "<a id=" not in result
        assert "vertex-" not in result

    def test_slug_is_derived_from_rendered_heading_text(self, tmp_path: Path) -> None:
        """Punctuation and inline markup drop out of the slug the way a GFM viewer drops them."""
        result = self._render(
            tmp_path, should_bundle=False, render_bundle=_heading_ref_bundle(second_title="What is a *Program*?")
        )
        assert "As [What is a *Program*?](#what-is-a-program) explains." in result

    def test_ambiguous_slug_falls_back_to_anchor(self, tmp_path: Path) -> None:
        """Two headings with the same slug keep the uid anchor above the referenced one."""
        result = self._render(tmp_path, should_bundle=False, render_bundle=_heading_ref_bundle(first_title="Second"))
        assert '<a id="vertex-head0002b"></a>\n\n## Second' in result
        assert "As [Second](#vertex-head0002b) explains." in result
        assert result.count("<a id=") == 1

    def test_empty_slug_falls_back_to_anchor(self, tmp_path: Path) -> None:
        """A heading whose text slugs to nothing keeps the uid anchor."""
        result = self._render(tmp_path, should_bundle=False, render_bundle=_heading_ref_bundle(second_title="???"))
        assert '<a id="vertex-head0002b"></a>\n\n## ???' in result
        assert "As [???](#vertex-head0002b) explains." in result

    def test_heading_links_off_italicizes_without_link(self, tmp_path: Path) -> None:
        """With heading_links=False the reference renders as the heading's text in italics, with no link or anchor."""
        result = self._render(tmp_path, should_bundle=False, heading_links=False)
        assert "As *Second* explains." in result
        assert "<a id=" not in result
        assert "(#second)" not in result


def _noted_bundle() -> RenderBundle:
    """A page whose prose carries a note link, with the note under a notes container."""
    note_url = vertex_link_url("note00001", VertexLinkKind.NOTE)
    page = PageVertex(uid="page00001", title="Doc", children=["prose0001", "notes0001"])
    prose = TextVertex(uid="prose0001", text=f"It ran for [a 52-minute run]({note_url}) and stopped.")
    notes = NotesVertex(uid="notes0001", children=["note00001"])
    note = TextVertex(uid="note00001", text="Williams and Kilburn, 1948.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, prose, notes, note]), view={})


class TestNotesInRunningText:
    """A note's lead-in stays plain running text; the notes container renders nothing where it sits."""

    @staticmethod
    def _render(tmp_path: Path, profile: ProjectProfile) -> str:
        render(
            _noted_bundle(),
            profile=profile,
            filename_stem="doc",
            api_endpoint=ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test"),
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_article_numbers_its_notes(self, tmp_path: Path) -> None:
        """An article's note renders as a GitHub footnote called right after its lead-in."""
        result: Final[str] = self._render(tmp_path, ArticleProfile())
        assert "It ran for a 52-minute run[^1] and stopped." in result
        assert "[^1]: Williams and Kilburn, 1948." in result
        assert "Notes" not in result
        assert "x-guffin" not in result

    def test_book_without_notes_section_gets_none(self, tmp_path: Path) -> None:
        """A book keeps invisible endnotes, so with no Notes section the lead-in stays plain and the note is absent."""
        result: Final[str] = self._render(tmp_path, BookProfile())
        assert "It ran for a 52-minute run and stopped." in result
        assert "Notes" not in result
        assert "Williams and Kilburn" not in result


def _callout_bundle(callout_type: CalloutVertex.CalloutType, title: str) -> RenderBundle:
    """A page holding one callout of *callout_type* titled *title*."""
    page = PageVertex(uid="page00001", title="Doc", children=["call00001"])
    callout = CalloutVertex(uid="call00001", callout_type=callout_type, title=title, body="Body line.")
    return RenderBundle(content=VertexTree(tree_vertices=[page, callout]), view={})


class TestCalloutTitleRendering:
    """A callout's title travels as a bold first line only when it says more than the alert's own label."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")

    def _render(self, tmp_path: Path, callout_type: CalloutVertex.CalloutType, title: str) -> str:
        render(
            _callout_bundle(callout_type, title),
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_informative_title_is_kept(self, tmp_path: Path) -> None:
        """A title the author wrote stays as the bold line under the marker."""
        result = self._render(tmp_path, CalloutVertex.CalloutType.INFO, "Read this first")
        assert "> [!NOTE]\n> **Read this first**\n>\n> Body line." in result

    def test_title_equal_to_type_keyword_is_dropped(self, tmp_path: Path) -> None:
        """A title that is only the callout's type keyword adds nothing to the alert and is omitted."""
        result = self._render(tmp_path, CalloutVertex.CalloutType.INFO, "INFO")
        assert "> [!NOTE]\n>\n> Body line." in result
        assert "**INFO**" not in result

    def test_title_equal_to_alert_label_is_dropped(self, tmp_path: Path) -> None:
        """A title that repeats the alert's own label, in any case, is omitted."""
        result = self._render(tmp_path, CalloutVertex.CalloutType.NOTE, "Note")
        assert "> [!NOTE]\n>\n> Body line." in result
        assert "**Note**" not in result

    def test_label_of_mapped_type_is_also_redundant(self, tmp_path: Path) -> None:
        """A callout type that maps onto a different GFM type treats that type's label as redundant too."""
        result = self._render(tmp_path, CalloutVertex.CalloutType.EXAMPLE, "note")
        assert "> [!NOTE]\n>\n> Body line." in result


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
            profile=ArticleProfile(),
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


class TestAlternatives:
    """Versioned blocks render their wordings as one glyph-led, line-per-wording block on request."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")
    _MUTED: Final[str] = '<span style="color: #737373; font-size: 0.93em">'

    def _render(
        self,
        tmp_path: Path,
        render_alternatives: bool,
        page_layout: ChildrenLayout = ChildrenLayout.DOCUMENT,
        alternative_text: str = "another *emphasized* wording",
    ) -> str:
        page = PageVertex(uid="page00001", title="Doc", children=["versed001"])
        versed = TextVertex(
            uid="versed001",
            text="the selected wording",
            alternatives=(Alternative(uid="altuid001", text=alternative_text),),
        )
        render(
            RenderBundle(
                content=VertexTree(tree_vertices=[page, versed]),
                view={"page00001": VertexView(children_layout=page_layout)},
            ),
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(
                output_dir=tmp_path, should_bundle=False, render_alternatives=render_alternatives
            ),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_default_renders_selected_wording_only(self, tmp_path: Path) -> None:
        """By default only the selected wording renders, with no glyph or group scaffold."""
        result = self._render(tmp_path, render_alternatives=False)
        assert "the selected wording" in result
        assert "another" not in result
        assert "◉" not in result
        assert "<div" not in result

    def test_paragraph_group_is_one_block_of_glyph_led_lines(self, tmp_path: Path) -> None:
        """In flow the wordings form one paragraph, a hard break between lines, the alternative muted."""
        result = self._render(tmp_path, render_alternatives=True)
        expected = f"◉ the selected wording  \n{self._MUTED}○ another *emphasized* wording</span>\n"
        assert expected in result
        assert "<div" not in result

    def test_list_item_group_continues_the_item(self, tmp_path: Path) -> None:
        """In a bullet list the wordings are the item's lines, the alternatives indented as its continuation."""
        result = self._render(tmp_path, render_alternatives=True, page_layout=ChildrenLayout.BULLET)
        assert f"- ◉ the selected wording  \n  {self._MUTED}○ another *emphasized* wording</span>\n" in result

    def test_non_inline_wording_falls_back_to_blocks(self, tmp_path: Path) -> None:
        """A wording holding a fenced code block cannot join one block, so the wordings render in sequence."""
        result = self._render(tmp_path, render_alternatives=True, alternative_text="see\n\n```python\nprint(1)\n```")
        assert "◉ the selected wording\n" in result
        assert f"{self._MUTED}○ see</span>" in result
        assert "print(1)" in result


class TestEpigraphAlternatives:
    """A versioned reference to epigraphs renders as ONE block quote, a glyph-led paragraph per epigraph."""

    _ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")
    _MUTED: Final[str] = '<span style="color: #a0a0a0; font-size: 0.93em">'

    @staticmethod
    def _reference(uid: str) -> str:
        return f"[> {uid}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"

    def _render(self, tmp_path: Path, alternative_text: str | None = None) -> str:
        epigraphs = [
            QuoteBlockVertex(uid=f"epigr000{n}", quote_type=QuoteType.EPIGRAPH, quote=quote, attribution=source)
            for n, quote, source in ((1, "Selected words.", "Dijkstra"), (2, "Other words.", "Perlis"))
        ]
        versed = TextVertex(
            uid="versed001",
            text=self._reference("epigr0001"),
            alternatives=(
                Alternative(
                    uid="altuid001",
                    text=self._reference("epigr0002") if alternative_text is None else alternative_text,
                ),
            ),
        )
        render(
            RenderBundle(
                content=VertexTree(
                    tree_vertices=[PageVertex(uid="page00001", title="Doc", children=["versed001"]), versed],
                    ref_vertices=epigraphs,
                ),
                view={},
            ),
            profile=ArticleProfile(),
            filename_stem="doc",
            api_endpoint=self._ENDPOINT,
            options=MarkdownRenderOptions(output_dir=tmp_path, should_bundle=False, render_alternatives=True),
        )
        return (tmp_path / "doc.md").read_text(encoding="utf-8")

    def test_group_is_one_block_quote_of_glyph_led_epigraphs(self, tmp_path: Path) -> None:
        """Each epigraph is one paragraph of the quote: glyph and italic quotation, a hard break, its source."""
        expected = (
            "> ◉ *Selected words.*  \n"
            "> —Dijkstra\n"
            ">\n"
            f"> {self._MUTED}○ *Other words.*</span>  \n"
            f"> {self._MUTED}—Perlis</span>\n"
        )
        assert expected in self._render(tmp_path)

    def test_plain_alternative_falls_back_to_blocks(self, tmp_path: Path) -> None:
        """An alternative that is not a quotation leaves the group as glyph-led blocks in sequence."""
        result = self._render(tmp_path, alternative_text="a plain other wording")
        assert "> *Selected words.*" in result
        assert '<span style="color: #737373; font-size: 0.93em">○ a plain other wording</span>' in result


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

    def _render(self, tmp_path: Path, profile: BookProfile | ArticleProfile) -> str:
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
        result = self._render(tmp_path, ArticleProfile())
        assert "### About the Author" in result


class TestRemoveStrippedBundleAssets:
    """_remove_stripped_bundle_assets deletes only fully-stripped files, only inside the bundle."""

    def test_stripped_file_is_removed_and_others_stay(self, tmp_path: Path) -> None:
        """The named file leaves the bundle; every other fetched asset stays."""
        stripped_file = tmp_path / "gone.pdf"
        stripped_file.write_bytes(b"pdf-bytes")
        kept_file = tmp_path / "kept.pdf"
        kept_file.write_bytes(b"pdf-bytes")
        refs = {
            "abcdefghi": AssetRef(uid="abcdefghi", path=stripped_file, size=None),
            "bcdefghij": AssetRef(uid="bcdefghij", path=kept_file, size=None),
        }
        _remove_stripped_bundle_assets(tmp_path, refs, frozenset({"gone.pdf"}))
        assert not stripped_file.exists()
        assert kept_file.exists()

    def test_file_outside_the_bundle_dir_is_never_touched(self, tmp_path: Path) -> None:
        """Only files laid inside the bundle directory are removal candidates."""
        outside_dir = tmp_path / "elsewhere"
        outside_dir.mkdir()
        outside_file = outside_dir / "gone.pdf"
        outside_file.write_bytes(b"pdf-bytes")
        refs = {"abcdefghi": AssetRef(uid="abcdefghi", path=outside_file, size=None)}
        _remove_stripped_bundle_assets(tmp_path, refs, frozenset({"gone.pdf"}))
        assert outside_file.exists()
