"""Unit tests for guffin.pipeline.md_rendering."""

from pathlib import Path
from typing import Final

from guffin.common.filenames import shell_safe_filename
from guffin.pipeline.md_rendering import render
from guffin.pipeline.roam_tree_to_vertex_tree import build_view_map, transcribe
from guffin.model.render_doc import RenderDoc
from guffin.roam.local_api import ApiEndpoint

from conftest import FIXTURES_MD_DIR, article1_node_tree


class TestRenderArticleFixture:
    """Integration tests for the md_rendering Pandoc output path."""

    def test_article_fixture_renders_to_expected_markdown(self, tmp_path: Path) -> None:
        """Rendering article1 to a plain ``.md`` file matches the expected fixture.

        Exercises the full :func:`~guffin.pipeline.md_rendering.render` path with
        ``bundle=False`` — the same path used by ``tests/regen_fixtures.py`` to
        produce the expected fixture — so the production resolver and every GFM
        Lua filter are covered.  ``bundle=False`` never fetches images, so the
        supplied :class:`~guffin.roam.local_api.ApiEndpoint` is unused.
        """
        # render no longer normalizes; callers pass an already-safe stem.
        stem: Final[str] = shell_safe_filename("[[Test Article]] 1")
        node_tree = article1_node_tree()
        render_doc: Final[RenderDoc] = RenderDoc(content=transcribe(node_tree), view=build_view_map(node_tree))
        endpoint: Final[ApiEndpoint] = ApiEndpoint.from_parts(
            local_api_port=3333, graph_name="test", bearer_token="test"
        )
        render(render_doc, filename_stem=stem, output_dir=tmp_path, api_endpoint=endpoint, bundle=False)
        result: Final[str] = (tmp_path / f"{stem}.md").read_text(encoding="utf-8")
        expected: Final[str] = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert result == expected
