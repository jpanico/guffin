"""Unit tests for guffin.common.markdown."""

import pytest

from guffin.common.markdown import (
    MD_IMAGE_RE,
    contains_fenced_code_block,
    hard_broken_markdown,
    is_fenced_code_block,
    parse_fenced_code_block,
    unwrap_links,
)


class TestIsFencedCodeBlock:
    """Tests for is_fenced_code_block — CommonMark fenced-code-block detection."""

    def test_backtick_fence_closed(self) -> None:
        """Test that a backtick-fenced, closed block is recognized."""
        assert is_fenced_code_block("```\ncode\n```") is True

    def test_tilde_fence_closed(self) -> None:
        """Test that a tilde-fenced, closed block is recognized."""
        assert is_fenced_code_block("~~~\ncode\n~~~") is True

    def test_info_string_language(self) -> None:
        """Test that an opening fence with a language info string is recognized."""
        assert is_fenced_code_block("```python\nx = 1\n```") is True

    def test_unclosed_fence_is_true(self) -> None:
        """Test that an unclosed fence is valid, since the closing fence is optional."""
        assert is_fenced_code_block("```python\nx = 1") is True

    def test_four_space_indent_is_not_fence(self) -> None:
        """Test that four spaces of indentation makes it an indented block, not a fence."""
        assert is_fenced_code_block("    ```\ncode\n    ```") is False

    def test_prose_before_fence_is_false(self) -> None:
        """Test that text preceding the opening fence disqualifies the string."""
        assert is_fenced_code_block("see: ```\ncode\n```") is False

    def test_content_after_closing_fence_is_false(self) -> None:
        """Test that non-blank content after the closing fence disqualifies the string."""
        assert is_fenced_code_block("```\ncode\n```\nmore") is False

    def test_backtick_in_backtick_info_string_is_false(self) -> None:
        """Test that a backtick inside a backtick-fence info string is invalid."""
        assert is_fenced_code_block("```foo`bar\ncode\n```") is False

    def test_inline_code_is_false(self) -> None:
        """Test that single-backtick inline code is not a fenced code block."""
        assert is_fenced_code_block("`inline`") is False

    def test_empty_string_is_false(self) -> None:
        """Test that an empty string is not a fenced code block."""
        assert is_fenced_code_block("") is False


class TestContainsFencedCodeBlock:
    """Tests for contains_fenced_code_block — any-line opening-fence detection."""

    def test_whole_string_fence(self) -> None:
        """Test that a string that is itself a fenced code block is detected."""
        assert contains_fenced_code_block("```\ncode\n```") is True

    def test_fence_after_prose(self) -> None:
        """Test that a fence opening on a later line is detected (unlike is_fenced_code_block)."""
        assert contains_fenced_code_block("intro paragraph\n\n```python\nx = 1\n```") is True

    def test_tilde_fence(self) -> None:
        """Test that a tilde fence is detected, not only backticks."""
        assert contains_fenced_code_block("prose\n\n~~~\ncode\n~~~") is True

    def test_indented_fence(self) -> None:
        """Test that a fence indented up to three spaces is detected."""
        assert contains_fenced_code_block("prose\n\n   ```\ncode\n   ```") is True

    def test_four_space_indent_is_not_fence(self) -> None:
        """Test that four spaces of indentation is an indented block, not a fence."""
        assert contains_fenced_code_block("    ```\ncode") is False

    def test_mid_line_backticks_are_not_a_fence(self) -> None:
        """Test that a fence run not at line start (after other text) is not detected."""
        assert contains_fenced_code_block("see the ``` marker") is False

    def test_inline_code_is_false(self) -> None:
        """Test that single-backtick inline code is not a fenced code block."""
        assert contains_fenced_code_block("some `inline` code") is False

    def test_prose_only_is_false(self) -> None:
        """Test that fence-free prose is not detected."""
        assert contains_fenced_code_block("just a paragraph of text") is False

    def test_empty_string_is_false(self) -> None:
        """Test that an empty string contains no fenced code block."""
        assert contains_fenced_code_block("") is False


class TestParseFencedCodeBlock:
    """Tests for parse_fenced_code_block — extracting the info string and code content."""

    def test_normalized_block(self) -> None:
        """Test a block whose closing fence is on its own line."""
        assert parse_fenced_code_block("```python\ncode\n```") == ("python", "code")

    def test_raw_attached_closing_fence(self) -> None:
        """Test the Roam form where the closing fence is attached to the final line."""
        assert parse_fenced_code_block("```python\ncode```") == ("python", "code")

    def test_multiline_code_preserved(self) -> None:
        """Test that multi-line code content is preserved between the fences."""
        assert parse_fenced_code_block("```python\ndef f():\n    pass\n```") == ("python", "def f():\n    pass")

    def test_unterminated_block_runs_to_end(self) -> None:
        """Test that an unterminated fence yields all remaining lines as code."""
        assert parse_fenced_code_block("```python\nx = 1") == ("python", "x = 1")

    def test_no_info_string(self) -> None:
        """Test that a fence with no info string yields an empty info."""
        assert parse_fenced_code_block("```\ncode\n```") == ("", "code")

    def test_not_a_fence_raises(self) -> None:
        """Test that a string not opening with a fence raises ValueError."""
        with pytest.raises(ValueError):
            parse_fenced_code_block("not a code block")


class TestUnwrapLinks:
    """Tests for unwrap_links — reducing CommonMark inline links to their display text."""

    def test_single_link(self) -> None:
        """A lone link is replaced by its display text."""
        assert unwrap_links("[Test Article](x-guffin:vertex/abc)") == "Test Article"

    def test_link_among_text(self) -> None:
        """Surrounding text is preserved; only the link is unwrapped."""
        assert unwrap_links("see [the page](http://x) now") == "see the page now"

    def test_multiple_links(self) -> None:
        """Every link in the string is unwrapped."""
        assert unwrap_links("[a](u1) and [b](u2)") == "a and b"

    def test_no_links_unchanged(self) -> None:
        """A string with no links is returned unchanged."""
        assert unwrap_links("plain text, no links") == "plain text, no links"

    def test_empty_link_text(self) -> None:
        """A link with empty display text unwraps to the empty string."""
        assert unwrap_links("x[](u)y") == "xy"


class TestHardBrokenMarkdown:
    """hard_broken_markdown() rejoins lines so each survives a Markdown parse as its own line."""

    def test_plain_lines_join_with_hard_breaks(self) -> None:
        """Consecutive plain lines join into one hard-broken paragraph."""
        assert hard_broken_markdown("line one\nline two\nline three") == "line one\\\nline two\\\nline three"

    def test_single_line_is_unchanged(self) -> None:
        """A single line passes through untouched."""
        assert hard_broken_markdown("just one line") == "just one line"

    def test_empty_string_is_unchanged(self) -> None:
        """An empty string passes through untouched."""
        assert hard_broken_markdown("") == ""

    def test_plain_to_list_boundary_becomes_blank_line(self) -> None:
        """A plain line followed by a bullet line gets a blank-line block boundary."""
        assert hard_broken_markdown("intro\n- item") == "intro\n\n- item"

    def test_list_to_plain_boundary_becomes_blank_line(self) -> None:
        """A bullet line followed by a plain line gets a blank-line block boundary."""
        assert hard_broken_markdown("- item\noutro") == "- item\n\noutro"

    def test_consecutive_list_lines_stay_tight(self) -> None:
        """Consecutive bullet lines keep a single newline (a tight list)."""
        assert hard_broken_markdown("- one\n- two\n* three") == "- one\n- two\n* three"

    def test_blank_line_stays_a_paragraph_boundary(self) -> None:
        """An authored blank line remains a paragraph boundary, not a hard break."""
        assert hard_broken_markdown("para one\n\npara two") == "para one\n\npara two"


class TestMdImageRe:
    """MD_IMAGE_RE matches a CommonMark inline image and captures its alt text and destination."""

    def test_matches_image_with_alt(self) -> None:
        """A standard image match captures both named groups."""
        match = MD_IMAGE_RE.fullmatch("![the cover](https://example.com/cover.jpeg)")
        assert match is not None
        assert match.group("alt") == "the cover"
        assert match.group("url") == "https://example.com/cover.jpeg"

    def test_matches_empty_alt(self) -> None:
        """An empty alt text still matches (the form Roam stores for a pasted image)."""
        match = MD_IMAGE_RE.fullmatch("![](https://example.com/cover.jpeg)")
        assert match is not None
        assert match.group("alt") == ""

    def test_plain_link_is_not_an_image(self) -> None:
        """A CommonMark link without the leading bang does not fullmatch."""
        assert MD_IMAGE_RE.fullmatch("[text](https://example.com/)") is None
