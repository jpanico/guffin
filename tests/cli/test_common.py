"""Tests for guffin.cli.common."""

import textwrap

from guffin.common.code_language import CodeLanguage
from guffin.common.filenames import shell_safe_filename
from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.model.attribute import (
    Attribute,
    AttributeAssignment,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
)
from guffin.model.guffin_semantics import GuffinAttribute
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
from guffin.render.project import ProjectType

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
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "My_Page.default"

    def test_heading_uses_text(self) -> None:
        """A heading root derives its stem from the heading text."""
        tree = _tree(HeadingVertex(uid="headng001", text="Section One", heading_level=1))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "Section_One.default"

    def test_text_uses_text(self) -> None:
        """A text root derives its stem from the block text."""
        tree = _tree(TextVertex(uid="text00001", text="Some plain text"))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "Some_plain_text.default"

    def test_block_quote_uses_text(self) -> None:
        """A block-quote root derives its stem from the block text."""
        tree = _tree(BlockQuoteVertex(uid="quote0001", text="A quoted line"))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "A_quoted_line.default"

    def test_code_block_uses_code(self) -> None:
        """A code-block root derives its stem from the code content."""
        tree = _tree(CodeBlockVertex(uid="code00001", code="hello world", language=CodeLanguage.PYTHON))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "hello_world.default"

    def test_callout_prefers_title(self) -> None:
        """A callout root prefers its title when present."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="Important Note", body="some body"
        )
        assert deduce_out_file_stem(_tree(callout), ProjectType.DEFAULT) == "Important_Note.default"

    def test_callout_falls_back_to_body(self) -> None:
        """A callout root falls back to its body when the title is empty."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="", body="Fallback Body"
        )
        assert deduce_out_file_stem(_tree(callout), ProjectType.DEFAULT) == "Fallback_Body.default"

    def test_image_prefers_alt_text(self) -> None:
        """An image root prefers its alt text when present."""
        image = ImageVertex(
            uid="image0001",
            source=_IMAGE_URL,  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
            alt_text="A flower",
        )
        assert deduce_out_file_stem(_tree(image), ProjectType.DEFAULT) == "A_flower.default"

    def test_image_falls_back_to_file_name(self) -> None:
        """An image root falls back to its file name when alt text is absent."""
        image = ImageVertex(
            uid="image0001",
            source=_IMAGE_URL,  # type: ignore[arg-type]
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
            file_name="photo.jpeg",
        )
        assert deduce_out_file_stem(_tree(image), ProjectType.DEFAULT) == "photo.jpeg.default"

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
        assert (
            deduce_out_file_stem(_tree(image), ProjectType.DEFAULT)
            == shell_safe_filename(str(image.source)) + ".default"
        )

    def test_table_joins_first_row_cells(self) -> None:
        """A table root joins the first row's cell values with underscores."""
        table = Table(rows=(("Name", "Age"), ("Bob", "30")))
        tree = _tree(TableVertex(uid="table0001", table=table, table_style=TableStyle()))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "Name_Age.default"

    def test_block_embed_recurses_into_target(self) -> None:
        """A block-embed root derives its stem from the embedded (referenced) vertex."""
        target = TextVertex(uid="target001", text="Embedded Target")
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="target001"))
        tree = VertexTree(tree_vertices=[embed], ref_vertices=[target])
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "Embedded_Target.default"

    def test_appends_project_type(self) -> None:
        """The selected project type is appended as a ``.<type>`` segment before the extension."""
        tree = _tree(PageVertex(uid="page00001", title="My Page"))
        assert deduce_out_file_stem(tree, ProjectType.BOOK) == "My_Page.book"
        assert deduce_out_file_stem(tree, ProjectType.MANUSCRIPT) == "My_Page.manuscript"

    def test_long_basis_is_clipped(self) -> None:
        """A basis longer than 40 characters is shortened with a ``..._`` marker, then made shell-safe.

        The marker ends in ``_`` (retained by ``shell_safe_filename``, which strips only leading
        underscores) so that the appended ``.<type>`` segment reads ``..._.default`` rather than a
        run of dots ``....default``.
        """
        long_title = "This is a very long page title that certainly exceeds the limit"
        result = deduce_out_file_stem(_tree(PageVertex(uid="page00001", title=long_title)), ProjectType.DEFAULT)
        assert result == shell_safe_filename(textwrap.shorten(long_title, width=40, placeholder="..._")) + ".default"
        assert result.endswith("..._.default")

    def test_unwraps_markdown_links(self) -> None:
        """A rendered Markdown link in the basis is unwrapped to its text, dropping the URL."""
        # A page titled "[[Test Article]] 3" transcribes to a rendered page-ref link.
        tree = _tree(PageVertex(uid="page00001", title="[Test Article](x-guffin:vertex/LBFKibPIj) 3"))
        assert deduce_out_file_stem(tree, ProjectType.DEFAULT) == "Test_Article_3.default"

    def test_guffin_title_attribute_takes_precedence(self) -> None:
        """A guffin/title attribute on the root overrides the vertex's own title for the stem basis."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        page = PageVertex(
            uid="page00001",
            title="Page Title",
            attribute_assignments=[
                AttributeAssignment(
                    attribute=AttributeInstance(
                        definition=Attribute(name=GuffinAttribute.TITLE, domain=AttributeDomain.GUFFIN), link=link
                    ),
                    values=(LiteralValue(value="Override Title"),),
                )
            ],
        )
        assert deduce_out_file_stem(_tree(page), ProjectType.DEFAULT) == "Override_Title.default"

    def test_non_guffin_title_attribute_is_ignored(self) -> None:
        """A ``title`` attribute outside the guffin domain does not override the basis."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        page = PageVertex(
            uid="page00001",
            title="Page Title",
            attribute_assignments=[
                AttributeAssignment(
                    attribute=AttributeInstance(
                        definition=Attribute(name="title", domain=AttributeDomain.DEFAULT), link=link
                    ),
                    values=(LiteralValue(value="Override Title"),),
                )
            ],
        )
        assert deduce_out_file_stem(_tree(page), ProjectType.DEFAULT) == "Page_Title.default"
