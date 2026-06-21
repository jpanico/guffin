"""Unit tests for guffin.render.md_rendering."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
# Rationale: panflute has no type stubs, so all its symbols are typed as Unknown by pyright.
# The four suppressed rules are triggered entirely by that Unknown propagation — disabling them
# here avoids dozens of cascading false-positive errors without relaxing any other strict checks.

from io import StringIO
from typing import Final

import panflute as pf  # type: ignore[import-untyped]
import pypandoc  # type: ignore[import-untyped]

from guffin.link import VertexLink
from guffin.render.md_rendering import _GFM_CALLOUT_FILTER
from guffin.render.pandoc_rendering import resolve_vertex_links, vertex_tree_to_pandoc
from guffin.roam_tree_to_vertex_tree import transcribe
from guffin.vertex import Vertex
from guffin.vertex_tree import VertexTree

from conftest import FIXTURES_MD_DIR, article1_node_tree


def _strip_link(vertex_link: VertexLink, vertex: Vertex, display: list[pf.Inline]) -> list[pf.Inline]:
    return display


class TestRenderArticleFixture:
    """Integration tests for the md_rendering Pandoc output path."""

    def test_article_fixture_renders_to_expected_markdown(self) -> None:
        """Rendering article1 via Pandoc with the GFM callout filter matches the expected fixture."""
        vertex_tree: Final[VertexTree] = transcribe(article1_node_tree())
        doc = vertex_tree_to_pandoc(vertex_tree, {}, title_in_header=True)
        resolve_vertex_links(doc, vertex_tree, _strip_link)
        buf = StringIO()
        pf.dump(doc, output_stream=buf)  # type: ignore[no-untyped-call]
        result = pypandoc.convert_text(  # type: ignore[no-untyped-call]
            buf.getvalue(),
            "gfm",
            format="json",
            extra_args=["--wrap=none", f"--lua-filter={_GFM_CALLOUT_FILTER}"],
        )
        expected = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert result == expected
