"""Tests for guffin.render.pandoc_ast."""

from copy import deepcopy

import panflute as pf  # type: ignore[import-untyped]
import pytest

from guffin.model.vertex_link import VertexLinkKind, vertex_link_url
from guffin.render.pandoc_ast import detached_copy, parse_inline_md


def _deeply_nested_inline(depth: int) -> tuple[pf.Doc, pf.Str]:
    """Build a document nesting one Str *depth* Spans deep, returning it and that Str.

    Descends through the containers on the way back down, since panflute assigns an element's
    ``parent`` lazily, when the container it sits in is accessed.
    """
    node: pf.Inline = pf.Str("label.pdf")
    for _ in range(depth):
        node = pf.Span(node)
    doc = pf.Doc(pf.Para(node))
    innermost = list(doc.content)[0]
    while not isinstance(innermost, pf.Str):
        innermost = list(innermost.content)[0]
    return doc, innermost


class TestDetachedCopy:
    """Tests for detached_copy()."""

    def test_copy_is_independent_of_the_original(self) -> None:
        """Mutating a copy leaves the original untouched."""
        original = [pf.Emph(pf.Str("a")), pf.Str("b")]
        copied = detached_copy(original)
        copied[1].text = "changed"
        assert original[1].text == "b"

    def test_copy_is_parentless(self) -> None:
        """A copy carries no parent, so it is free to be placed elsewhere."""
        _, innermost = _deeply_nested_inline(3)
        assert detached_copy([innermost])[0].parent is None

    def test_originals_keep_their_place(self) -> None:
        """Copying does not detach the originals from the document they sit in."""
        _, innermost = _deeply_nested_inline(3)
        parent_before = innermost.parent
        detached_copy([innermost])
        assert innermost.parent is parent_before

    def test_does_not_copy_the_enclosing_document(self) -> None:
        """A copy is bounded by the element, not by the document holding it.

        Regression: a panflute element's ``parent`` back-reference makes a plain deepcopy walk the
        whole enclosing document, which exhausts the interpreter stack on a real export.
        """
        _, innermost = _deeply_nested_inline(2000)
        with pytest.raises(RecursionError):
            deepcopy([innermost])
        assert detached_copy([innermost])[0].text == "label.pdf"


@pytest.mark.pandoc
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

    def test_definition_marker_entry_does_not_misalign_following_entries(self) -> None:
        """An entry that is a lone ``~`` maps every entry — before, itself, and after — to its own text.

        Pandoc's definition_lists extension captures a preceding paragraph (even across a blank
        line) as the term of a ``~``-led definition; a paragraph separator would be swallowed and
        every following entry would map to its neighbour's inlines.
        """
        texts = ["before", "~", "first after", "second after"]
        result = parse_inline_md(texts)
        for text in texts:
            assert text in result
            assert pf.stringify(pf.Para(*result[text])).strip() == text

    def test_colon_led_entry_does_not_misalign_following_entries(self) -> None:
        """A ``:``-led entry (Pandoc's other definition marker) does not shift later entries."""
        texts = ["before", ": colon led", "after"]
        result = parse_inline_md(texts)
        assert pf.stringify(pf.Para(*result["before"])).strip() == "before"
        assert pf.stringify(pf.Para(*result["after"])).strip() == "after"

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
