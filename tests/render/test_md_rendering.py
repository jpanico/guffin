"""Unit tests for guffin.render.md_rendering."""

from pathlib import Path
from typing import Final

import pytest
from conftest import FIXTURES_MD_DIR, article1_node_tree

from guffin.common.filenames import shell_safe_filename
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import HeadingVertex, PageVertex, TextVertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
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

    def test_titleless_document_keeps_heading_levels(self, tmp_path: Path) -> None:
        """A subtree export with no document title leaves its level-1 headings at H1."""
        root = HeadingVertex(uid="root00001", text="Notes", heading_level=1, children=["chap00001"])
        chapter = HeadingVertex(uid="chap00001", text="Chapter I", heading_level=1, children=["text00001"])
        text = TextVertex(uid="text00001", text="Some prose.")
        bundle = RenderBundle(content=VertexTree(tree_vertices=[root, chapter, text]), view={})
        result = self._render_bundle(tmp_path, bundle)
        assert result.startswith("# Chapter I\n")
