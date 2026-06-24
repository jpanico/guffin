"""Tests for guffin.cli.common."""

import textwrap

from guffin.common.code_language import CodeLanguage
from guffin.common.filenames import shell_safe_filename
from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import (
    BlockEmbedVertex,
    BlockQuoteVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TableVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_tree import VertexTree

from guffin.cli.common import deduce_out_file_stem

_IMAGE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)


def _tree(root: Vertex) -> VertexTree:
    """Wrap a single root vertex in a VertexTree."""
    return VertexTree(tree_vertices=[root])


class TestDeduceOutFileStem:
    """Tests for deduce_out_file_stem()."""

    def test_page_uses_title(self) -> None:
        """A page root derives its stem from the page title."""
        tree = _tree(PageVertex(uid="page00001", title="My Page"))
        assert deduce_out_file_stem(tree) == "My_Page"

    def test_heading_uses_text(self) -> None:
        """A heading root derives its stem from the heading text."""
        tree = _tree(HeadingVertex(uid="headng001", text="Section One", heading_level=1))
        assert deduce_out_file_stem(tree) == "Section_One"

    def test_text_uses_text(self) -> None:
        """A text root derives its stem from the block text."""
        tree = _tree(TextVertex(uid="text00001", text="Some plain text"))
        assert deduce_out_file_stem(tree) == "Some_plain_text"

    def test_block_quote_uses_text(self) -> None:
        """A block-quote root derives its stem from the block text."""
        tree = _tree(BlockQuoteVertex(uid="quote0001", text="A quoted line"))
        assert deduce_out_file_stem(tree) == "A_quoted_line"

    def test_code_block_uses_code(self) -> None:
        """A code-block root derives its stem from the code content."""
        tree = _tree(CodeBlockVertex(uid="code00001", code="hello world", language=CodeLanguage.PYTHON))
        assert deduce_out_file_stem(tree) == "hello_world"

    def test_callout_prefers_title(self) -> None:
        """A callout root prefers its title when present."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="Important Note", body="some body"
        )
        assert deduce_out_file_stem(_tree(callout)) == "Important_Note"

    def test_callout_falls_back_to_body(self) -> None:
        """A callout root falls back to its body when the title is empty."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="", body="Fallback Body"
        )
        assert deduce_out_file_stem(_tree(callout)) == "Fallback_Body"

    def test_image_prefers_alt_text(self) -> None:
        """An image root prefers its alt text when present."""
        image = ImageVertex(
            uid="image0001",
            source=_IMAGE_URL,  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
            alt_text="A flower",
        )
        assert deduce_out_file_stem(_tree(image)) == "A_flower"

    def test_image_falls_back_to_file_name(self) -> None:
        """An image root falls back to its file name when alt text is absent."""
        image = ImageVertex(
            uid="image0001",
            source=_IMAGE_URL,  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
            file_name="photo.jpeg",
        )
        assert deduce_out_file_stem(_tree(image)) == "photo.jpeg"

    def test_image_falls_back_to_source(self) -> None:
        """An image root falls back to its source URL when alt text and file name are absent."""
        # A short URL so textwrap.shorten leaves it intact (a long URL is one unbreakable
        # "word" and would collapse to the ellipsis placeholder).
        image = ImageVertex(
            uid="image0001",
            source="http://example.com/p.jpg",  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        assert deduce_out_file_stem(_tree(image)) == shell_safe_filename(str(image.source))

    def test_table_joins_first_row_cells(self) -> None:
        """A table root joins the first row's cell values with underscores."""
        table = Table(rows=(("Name", "Age"), ("Bob", "30")))
        tree = _tree(TableVertex(uid="table0001", table=table, table_style=TableStyle()))
        assert deduce_out_file_stem(tree) == "Name_Age"

    def test_block_embed_recurses_into_target(self) -> None:
        """A block-embed root derives its stem from the embedded (referenced) vertex."""
        target = TextVertex(uid="target001", text="Embedded Target")
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="target001"))
        tree = VertexTree(tree_vertices=[embed], ref_vertices=[target])
        assert deduce_out_file_stem(tree) == "Embedded_Target"

    def test_long_basis_is_clipped(self) -> None:
        """A basis longer than 40 characters is shortened with an ellipsis, then made shell-safe."""
        long_title = "This is a very long page title that certainly exceeds the limit"
        result = deduce_out_file_stem(_tree(PageVertex(uid="page00001", title=long_title)))
        assert result == shell_safe_filename(textwrap.shorten(long_title, width=40, placeholder="..."))
        assert result.endswith("...")

    def test_unwraps_markdown_links(self) -> None:
        """A rendered Markdown link in the basis is unwrapped to its text, dropping the URL."""
        # A page titled "[[Test Article]] 3" transcribes to a rendered page-ref link.
        tree = _tree(PageVertex(uid="page00001", title="[Test Article](x-guffin:vertex/LBFKibPIj) 3"))
        assert deduce_out_file_stem(tree) == "Test_Article_3"
