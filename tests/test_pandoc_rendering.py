"""Unit tests for guffin.pipeline.pandoc_rendering."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false
# Rationale: panflute has no type stubs; all six rules are triggered entirely by
# Unknown propagation from that import — suppressing them here avoids false positives.

from pathlib import Path

import panflute as pf  # type: ignore[import-untyped]
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.vertex import (
    HeadingVertex,
    ImageVertex,
    PageVertex,
    TextVertex,
)
from guffin.model.vertex_tree import VertexTree
from guffin.model.link import VertexLinkKind, vertex_link_url
from guffin.pipeline.pandoc_rendering import (
    parse_inline_md,
    build_child_blocks,
    vertex_tree_to_pandoc,
)

from conftest import article1_vertex_tree

_IMAGE_URL: HttpUrl = HttpUrl("https://example.com/imgs/photo.jpeg")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_text(element: pf.Element) -> str:
    """Reconstruct plain text from panflute Str, Space, and SoftBreak inlines."""
    parts: list[str] = []
    for inline in element.content:
        if isinstance(inline, pf.Str):
            parts.append(inline.text)
        elif isinstance(inline, (pf.Space, pf.SoftBreak)):
            parts.append(" ")
    return "".join(parts)


# ---------------------------------------------------------------------------
# TestParseInlineMd
# ---------------------------------------------------------------------------


class TestParseInlineMd:
    """Tests for parse_inline_md()."""

    def test_empty_input_returns_empty_dict(self) -> None:
        """An empty text list produces an empty mapping."""
        assert parse_inline_md([]) == {}

    def test_all_empty_strings_returns_empty_dict(self) -> None:
        """A list of only empty strings produces an empty mapping."""
        assert parse_inline_md(["", "", ""]) == {}

    def test_plain_text_parses_to_str_inlines(self) -> None:
        """Plain text produces Str and Space inline elements."""
        result = parse_inline_md(["hello world"])
        assert "hello world" in result
        text = "".join(
            i.text if isinstance(i, pf.Str) else " " for i in result["hello world"] if isinstance(i, (pf.Str, pf.Space))
        )
        assert text == "hello world"

    def test_bold_text_parses_to_strong(self) -> None:
        """Pandoc Markdown bold syntax produces a Strong inline."""
        result = parse_inline_md(["**bold**"])
        assert "**bold**" in result
        inlines = result["**bold**"]
        assert any(isinstance(i, pf.Strong) for i in inlines)

    def test_italic_text_parses_to_emph(self) -> None:
        """Pandoc Markdown italic syntax produces an Emph inline."""
        result = parse_inline_md(["*italic*"])
        assert "*italic*" in result
        inlines = result["*italic*"]
        assert any(isinstance(i, pf.Emph) for i in inlines)

    def test_code_span_parses_to_code(self) -> None:
        """Pandoc Markdown code span produces a Code inline."""
        result = parse_inline_md(["`code`"])
        assert "`code`" in result
        inlines = result["`code`"]
        assert any(isinstance(i, pf.Code) for i in inlines)

    def test_multiple_texts_all_present(self) -> None:
        """Multiple distinct texts all appear in the result mapping."""
        texts = ["first", "**second**", "*third*"]
        result = parse_inline_md(texts)
        for t in texts:
            assert t in result

    def test_duplicate_texts_deduplicated(self) -> None:
        """Duplicate texts produce a single entry in the mapping."""
        result = parse_inline_md(["hello", "hello", "hello"])
        assert len(result) == 1
        assert "hello" in result

    def test_empty_strings_ignored(self) -> None:
        """Empty strings do not appear in the result mapping."""
        result = parse_inline_md(["hello", "", "world"])
        assert "" not in result
        assert "hello" in result
        assert "world" in result

    def test_link_parses_to_link_inline(self) -> None:
        """Markdown link syntax produces a Link inline element."""
        result = parse_inline_md(["[click here](https://example.com)"])
        assert "[click here](https://example.com)" in result
        inlines = result["[click here](https://example.com)"]
        assert any(isinstance(i, pf.Link) for i in inlines)

    def test_link_display_text_is_preserved(self) -> None:
        """The display text of a Markdown link is preserved in the Link element's content."""
        result = parse_inline_md(["[click here](https://example.com)"])
        inlines = result["[click here](https://example.com)"]
        link = next(i for i in inlines if isinstance(i, pf.Link))
        text = "".join(i.text for i in link.content if isinstance(i, pf.Str))
        assert "click" in text and "here" in text

    def test_strikethrough_parses_to_strikeout(self) -> None:
        """Pandoc Markdown strikethrough syntax produces a Strikeout inline."""
        result = parse_inline_md(["~~gone~~"])
        assert "~~gone~~" in result
        inlines = result["~~gone~~"]
        assert any(isinstance(i, pf.Strikeout) for i in inlines)

    def test_non_paragraph_block_absent_from_result(self) -> None:
        """A string that Pandoc parses as a non-paragraph block (e.g. '---') is absent from the result."""
        result = parse_inline_md(["---"])
        assert "---" not in result

    def test_non_paragraph_block_does_not_discard_surrounding_entries(self) -> None:
        """A non-paragraph entry does not cause adjacent entries to be dropped."""
        result = parse_inline_md(["before", "---", "after"])
        assert "before" in result
        assert "after" in result

    def test_deduplication_preserves_insertion_order(self) -> None:
        """Duplicate entries are dropped but first-seen insertion order is maintained."""
        result = parse_inline_md(["charlie", "alpha", "bravo", "alpha", "charlie"])
        assert list(result.keys()) == ["charlie", "alpha", "bravo"]

    def test_each_result_value_is_nonempty_list(self) -> None:
        """Every key in the result maps to a non-empty list of inline elements."""
        result = parse_inline_md(["hello", "**bold**", "*italic*"])
        for inlines in result.values():
            assert isinstance(inlines, list)
            assert len(inlines) > 0

    def test_standalone_x_guffin_link_parses_to_pf_link(self) -> None:
        """A standalone x-guffin link produces a Link inline whose url is the x-guffin URL."""
        uid: str = "abc123xyz"
        url: str = vertex_link_url(uid, VertexLinkKind.REFERENCE)
        md: str = f"[My Page]({url})"
        result: dict[str, list[pf.Inline]] = parse_inline_md([md])
        assert md in result
        inlines: list[pf.Inline] = result[md]
        links: list[pf.Link] = [i for i in inlines if isinstance(i, pf.Link)]
        assert len(links) == 1
        assert links[0].url == url

    def test_embedded_x_guffin_link_produces_pf_link(self) -> None:
        """An x-guffin link embedded in prose produces a Link inline with the correct url and display text."""
        uid = "abc123xyz"
        url = vertex_link_url(uid, VertexLinkKind.REFERENCE)
        md = f"See [My Page]({url}) for details."
        result = parse_inline_md([md])
        assert md in result
        inlines = result[md]
        links = [i for i in inlines if isinstance(i, pf.Link)]
        assert len(links) == 1
        assert links[0].url == url
        display = "".join(i.text for i in links[0].content if isinstance(i, pf.Str))
        assert "My" in display and "Page" in display


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocPageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocPageVertex:
    """Tests for vertex_tree_to_pandoc() — PageVertex root behaviour."""

    def test_page_title_set_in_metadata(self) -> None:
        """Page title appears as the Pandoc metadata title (default title_in_header=False)."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="My Page")])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        assert "title" in doc.metadata
        assert _collect_text(doc.metadata["title"]) == "My Page"

    def test_page_with_no_children_produces_no_blocks(self) -> None:
        """A bare PageVertex with no children produces an empty document body."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="Empty")])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        assert list(doc.content) == []

    def test_non_page_root_produces_no_metadata_title(self) -> None:
        """When the root is not a PageVertex, no metadata title is set."""
        tree = VertexTree(tree_vertices=[HeadingVertex(uid="head00001", text="Intro", heading_level=1)])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        assert "title" not in doc.metadata

    def test_title_in_header_renders_h1_not_metadata(self) -> None:
        """title_in_header=True renders page title as H1 body block, not metadata."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="page00001", title="My Page")])
        doc, _ = vertex_tree_to_pandoc(tree, {}, title_in_header=True)
        assert "title" not in doc.metadata
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 1
        assert _collect_text(blocks[0]) == "My Page"

    def test_title_in_header_includes_children_after_h1(self) -> None:
        """title_in_header=True: H1 is followed by rendered children."""
        page = PageVertex(uid="page00001", title="Doc", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section", heading_level=2)
        tree = VertexTree(tree_vertices=[page, heading])
        doc, _ = vertex_tree_to_pandoc(tree, {}, title_in_header=True)
        blocks = list(doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 1
        assert isinstance(blocks[1], pf.Header)
        assert blocks[1].level == 2


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocHeadingVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocHeadingVertex:
    """Tests for vertex_tree_to_pandoc() — HeadingVertex rendering."""

    def test_heading_level_preserved(self) -> None:
        """HeadingVertex produces a Header block at the recorded heading level."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section 1", heading_level=2)
        tree = VertexTree(tree_vertices=[page, heading])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert _collect_text(blocks[0]) == "Section 1"

    def test_h3_heading(self) -> None:
        """HeadingVertex at level 3 produces an H3 Header."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Subsection", heading_level=3)
        tree = VertexTree(tree_vertices=[page, heading])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 3

    def test_h4_through_h6(self) -> None:
        """HeadingVertices at levels 4, 5, 6 produce Headers at the correct levels."""
        page = PageVertex(uid="page00001", title="P", children=["head0004a", "head0005a", "head0006a"])
        h4 = HeadingVertex(uid="head0004a", text="H4", heading_level=4)
        h5 = HeadingVertex(uid="head0005a", text="H5", heading_level=5)
        h6 = HeadingVertex(uid="head0006a", text="H6", heading_level=6)
        tree = VertexTree(tree_vertices=[page, h4, h5, h6])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert [b.level for b in blocks] == [4, 5, 6]

    def test_nested_headings_flattened_into_document(self) -> None:
        """Children of a HeadingVertex are rendered as sibling blocks, not nested."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        h2 = HeadingVertex(uid="head0001a", text="Chapter", heading_level=2, children=["head0001b"])
        h3 = HeadingVertex(uid="head0001b", text="Section", heading_level=3)
        tree = VertexTree(tree_vertices=[page, h2, h3])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[0], pf.Header)
        assert blocks[0].level == 2
        assert _collect_text(blocks[0]) == "Chapter"
        assert isinstance(blocks[1], pf.Header)
        assert blocks[1].level == 3
        assert _collect_text(blocks[1]) == "Section"


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocText
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocText:
    """Tests for vertex_tree_to_pandoc() — TextVertex rendering."""

    def test_depth_1_is_para(self) -> None:
        """A TextVertex that is a direct child of the page renders as a Para."""
        page = PageVertex(uid="page00001", title="P", children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="Hello world")
        tree = VertexTree(tree_vertices=[page, block])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        assert _collect_text(blocks[0]) == "Hello world"

    def test_depth_2_text_under_heading_is_bullet(self) -> None:
        """A TextVertex under a HeadingVertex (depth 2) renders as a BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="Section", heading_level=2, children=["txt00001a"])
        block = TextVertex(uid="txt00001a", text="Body text")
        tree = VertexTree(tree_vertices=[page, heading, block])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        assert len(blocks) == 2
        assert isinstance(blocks[1], pf.BulletList)
        items = list(blocks[1].content)
        assert len(items) == 1
        assert isinstance(items[0], pf.ListItem)
        item_blocks = list(items[0].content)
        assert isinstance(item_blocks[0], pf.Plain)
        assert _collect_text(item_blocks[0]) == "Body text"

    def test_nested_text_produces_nested_bullet_list(self) -> None:
        """A TextVertex child of another TextVertex renders as a nested BulletList."""
        page = PageVertex(uid="page00001", title="P", children=["head0001a"])
        heading = HeadingVertex(uid="head0001a", text="S", heading_level=2, children=["txt00001a"])
        parent = TextVertex(uid="txt00001a", text="Parent", children=["txt00001b"])
        child = TextVertex(uid="txt00001b", text="Child")
        tree = VertexTree(tree_vertices=[page, heading, parent, child])
        _doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(_doc.content)
        bullet_list = blocks[1]
        assert isinstance(bullet_list, pf.BulletList)
        parent_item = list(bullet_list.content)[0]
        parent_item_blocks = list(parent_item.content)
        assert len(parent_item_blocks) == 2
        nested_list = parent_item_blocks[1]
        assert isinstance(nested_list, pf.BulletList)
        child_item = list(nested_list.content)[0]
        assert _collect_text(list(child_item.content)[0]) == "Child"


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocImageVertex
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocImageVertex:
    """Tests for vertex_tree_to_pandoc() — ImageVertex rendering."""

    def test_fetched_image_is_embedded(self, tmp_path: Path) -> None:
        """When image_files has an entry for the vertex, a pf.Image is used."""
        fake_img = tmp_path / "photo.jpg"
        fake_img.write_bytes(b"")
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {"img00001a": fake_img})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Image)
        assert inline.url == str(fake_img)

    def test_unfetched_image_falls_back_to_link(self) -> None:
        """When image_files has no entry for the vertex, a pf.Link is used."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        blocks = list(doc.content)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)
        inline = list(blocks[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert inline.url == str(_IMAGE_URL)

    def test_unfetched_image_link_label_uses_alt_text(self) -> None:
        """The fallback link label uses alt_text when present."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            alt_text="A flower",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _collect_text(inline) == "A flower"

    def test_unfetched_image_link_label_falls_back_to_file_name(self) -> None:
        """The fallback link label uses file_name when alt_text is absent."""
        page = PageVertex(uid="page00001", title="P", children=["img00001a"])
        image = ImageVertex(
            uid="img00001a",
            source=_IMAGE_URL,
            file_name="photo.jpg",
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        tree = VertexTree(tree_vertices=[page, image])
        doc, _ = vertex_tree_to_pandoc(tree, {})
        inline = list(list(doc.content)[0].content)[0]
        assert isinstance(inline, pf.Link)
        assert _collect_text(inline) == "photo.jpg"


# ---------------------------------------------------------------------------
# TestBuildBlocksCoalescing
# ---------------------------------------------------------------------------


class TestBuildBlocksCoalescing:
    """Tests for build_child_blocks() — sibling TextVertex coalescing."""

    def test_consecutive_text_siblings_coalesced_into_one_bullet_list(self) -> None:
        """Two consecutive TextVertex siblings at depth 2 produce a single BulletList."""
        t1 = TextVertex(uid="txt000001", text="Item 1")
        t2 = TextVertex(uid="txt000002", text="Item 2")
        blocks = build_child_blocks(["txt000001", "txt000002"], VertexTree(tree_vertices=[t1, t2]), {}, {}, depth=2)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.BulletList)
        assert len(list(blocks[0].content)) == 2

    def test_heading_between_text_siblings_splits_bullet_lists(self) -> None:
        """A HeadingVertex between two TextContentVertices produces two separate BulletLists."""
        t1 = TextVertex(uid="txt000001", text="Before")
        h = HeadingVertex(uid="head00001", text="Break", heading_level=3)
        t2 = TextVertex(uid="txt000002", text="After")
        blocks = build_child_blocks(
            ["txt000001", "head00001", "txt000002"], VertexTree(tree_vertices=[t1, h, t2]), {}, {}, depth=2
        )
        assert len(blocks) == 3
        assert isinstance(blocks[0], pf.BulletList)
        assert isinstance(blocks[1], pf.Header)
        assert isinstance(blocks[2], pf.BulletList)

    def test_text_at_depth_1_is_not_coalesced_into_bullet_list(self) -> None:
        """TextContentVertices at depth 1 render as Paras, not BulletList items."""
        t1 = TextVertex(uid="txt000001", text="Para 1")
        t2 = TextVertex(uid="txt000002", text="Para 2")
        blocks = build_child_blocks(["txt000001", "txt000002"], VertexTree(tree_vertices=[t1, t2]), {}, {}, depth=1)
        assert len(blocks) == 2
        assert all(isinstance(b, pf.Para) for b in blocks)

    def test_unknown_uid_is_skipped(self) -> None:
        """A UID absent from vertex_tree is silently skipped."""
        t1 = TextVertex(uid="txt000001", text="Present")
        blocks = build_child_blocks(["missingXY", "txt000001"], VertexTree(tree_vertices=[t1]), {}, {}, depth=1)
        assert len(blocks) == 1
        assert isinstance(blocks[0], pf.Para)


# ---------------------------------------------------------------------------
# TestVertexTreeToPandocArticleFixture
# ---------------------------------------------------------------------------


class TestVertexTreeToPandocArticleFixture:
    """Integration tests for vertex_tree_to_pandoc() using the Test Article 1 fixture."""

    def test_metadata_title_is_test_article_1(self) -> None:
        """Doc metadata title matches the page title from the fixture."""
        doc, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {})
        assert _collect_text(doc.metadata["title"]) == "Test Article 1"

    def test_block_count(self) -> None:
        """The fixture produces the expected number of top-level blocks."""
        doc, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {})
        # 1 Div(callout) + 3 H1s + 4 H2s + 3 H3s + 1 H4 + 2 Para(Link) + 3 BulletList = 17
        assert len(list(doc.content)) == 17

    def test_first_block_is_section_1_header(self) -> None:
        """The second block is an H1 Header for 'Section 1' (first block is the callout Para)."""
        doc, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {})
        second = list(doc.content)[1]
        assert isinstance(second, pf.Header)
        assert second.level == 1
        assert _collect_text(second) == "Section 1"

    def test_image_renders_as_fallback_link_when_no_image_files(self) -> None:
        """The ImageVertex in the fixture renders as a pf.Link when image_files is empty."""
        doc, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {})
        blocks = list(doc.content)
        image_para = next(
            (b for b in blocks if isinstance(b, pf.Para) and isinstance(list(b.content)[0], pf.Link)), None
        )
        assert image_para is not None

    def test_text_content_vertex_renders_as_bullet_list(self) -> None:
        """Each TextVertex renders as a top-level BulletList."""
        doc, _ = vertex_tree_to_pandoc(article1_vertex_tree(), {})
        blocks = list(doc.content)
        bullet_lists = [b for b in blocks if isinstance(b, pf.BulletList)]
        assert len(bullet_lists) == 3
        items = list(bullet_lists[1].content)
        assert len(items) == 1
        assert _collect_text(list(items[0].content)[0]) == "AI assistant (Claude Opus 4.6):"
