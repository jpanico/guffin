"""Unit tests for guffin.common.markdown."""

import pytest

from guffin.common.markdown import is_fenced_code_block, parse_fenced_code_block


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
