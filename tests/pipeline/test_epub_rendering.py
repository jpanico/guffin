"""Tests for guffin.pipeline.epub_rendering."""

import zipfile
from pathlib import Path
from typing import Final

from guffin.common.filenames import shell_safe_filename
from guffin.model.render_bundle import RenderBundle
from guffin.pipeline.epub_rendering import render
from guffin.pipeline.render_options import EpubRenderOptions
from guffin.pipeline.roam_tree_to_guffin import build_view_map, transcribe
from guffin.roam.local_api import ApiEndpoint

from conftest import article5_node_tree

_ENDPOINT: Final[ApiEndpoint] = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="test")


def _article5_bundle() -> RenderBundle:
    """Build the image-free ``[[Test Article]] 5`` render bundle (keeps the test offline)."""
    node_tree = article5_node_tree()
    return RenderBundle(content=transcribe(node_tree), view=build_view_map(node_tree))


class TestRenderEpub:
    """Integration tests for the epub_rendering Pandoc output path.

    ``[[Test Article]] 5`` contains no images, so :func:`~guffin.pipeline.epub_rendering.render`
    fetches nothing and the supplied :class:`~guffin.roam.local_api.ApiEndpoint` is never called.
    """

    def test_produces_valid_epub_package(self, tmp_path: Path) -> None:
        """Rendering article5 yields a well-formed EPUB OCF container with the page title."""
        stem: Final[str] = shell_safe_filename("[[Test Article]] 5")
        render(
            _article5_bundle(),
            filename_stem=stem,
            api_endpoint=_ENDPOINT,
            options=EpubRenderOptions(output_dir=tmp_path),
        )
        epub_path: Final[Path] = tmp_path / f"{stem}.epub"
        assert epub_path.is_file()
        with zipfile.ZipFile(epub_path) as zf:
            # OCF requires a literal `application/epub+zip` mimetype entry.
            assert zf.read("mimetype") == b"application/epub+zip"
            names: Final[list[str]] = zf.namelist()
            assert any(name.endswith("nav.xhtml") for name in names)
            assert any(name.endswith(".opf") for name in names)
            assert any(name.endswith(".xhtml") and "ch" in name for name in names)
            opf: Final[str] = zf.read(next(name for name in names if name.endswith(".opf"))).decode("utf-8")
            assert "Test Article 5" in opf

    def test_preserves_pill_styling(self, tmp_path: Path) -> None:
        """Attribute reference values render as inline-styled pill spans in the EPUB XHTML."""
        stem: Final[str] = shell_safe_filename("[[Test Article]] 5")
        render(
            _article5_bundle(),
            filename_stem=stem,
            api_endpoint=_ENDPOINT,
            options=EpubRenderOptions(output_dir=tmp_path),
        )
        with zipfile.ZipFile(tmp_path / f"{stem}.epub") as zf:
            chapter: Final[str] = next(
                zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith(".xhtml") and "ch" in name
            )
            assert "background-color: #FF851C" in chapter

    def test_suppress_attributes_drops_pills(self, tmp_path: Path) -> None:
        """With suppress_attributes, the attribute pills are absent from the EPUB."""
        stem: Final[str] = shell_safe_filename("[[Test Article]] 5")
        render(
            _article5_bundle(),
            filename_stem=stem,
            api_endpoint=_ENDPOINT,
            options=EpubRenderOptions(output_dir=tmp_path, suppress_attributes=True),
        )
        with zipfile.ZipFile(tmp_path / f"{stem}.epub") as zf:
            chapter: Final[str] = next(
                zf.read(name).decode("utf-8") for name in zf.namelist() if name.endswith(".xhtml") and "ch" in name
            )
            assert "background-color: #FF851C" not in chapter
