"""Unit tests for guffin.render.md_post_processing."""

from guffin.render.md_post_processing import indent_fenced_blank_lines, strip_list_separator_comments


class TestStripListSeparatorComments:
    """Tests for strip_list_separator_comments."""

    def test_separator_comment_collapses_to_one_paragraph_break(self) -> None:
        """A blank-line-padded ``<!-- -->`` comment between lists becomes a single break."""
        gfm = "- one\n\n<!-- -->\n\n- two\n"
        assert strip_list_separator_comments(gfm) == "- one\n\n- two\n"

    def test_text_without_separators_is_unchanged(self) -> None:
        """A string carrying no separator comment passes through verbatim."""
        gfm = "- one\n\n- two\n"
        assert strip_list_separator_comments(gfm) == gfm


class TestIndentFencedBlankLines:
    """Tests for indent_fenced_blank_lines."""

    def test_blank_lines_inside_an_indented_fence_gain_its_indentation(self) -> None:
        """An empty line between an indented fence's markers becomes the fence's indentation."""
        gfm = "- item\n\n      ``` python\n      first\n\n      second\n      ```\n"
        expected = "- item\n\n      ``` python\n      first\n      \n      second\n      ```\n"
        assert indent_fenced_blank_lines(gfm) == expected

    def test_every_blank_line_in_the_fence_is_padded(self) -> None:
        """Each of several blank-line-separated sections stays inside the one fence."""
        gfm = "  - x\n    ``` python\n    a\n\n    b\n\n    c\n    ```\n"
        expected = "  - x\n    ``` python\n    a\n    \n    b\n    \n    c\n    ```\n"
        assert indent_fenced_blank_lines(gfm) == expected

    def test_unindented_fence_is_unchanged(self) -> None:
        """A top-level fence's blank lines carry no indentation, so nothing changes."""
        gfm = "``` python\nfirst\n\nsecond\n```\n"
        assert indent_fenced_blank_lines(gfm) == gfm

    def test_blank_lines_outside_fences_are_untouched(self) -> None:
        """Blank lines in ordinary prose stay empty."""
        gfm = "- item\n\n      ``` python\n      code\n      ```\n\nafter\n\nmore\n"
        assert indent_fenced_blank_lines(gfm) == gfm

    def test_whitespace_only_code_lines_stay_verbatim(self) -> None:
        """A whitespace-only line inside a fence is code content, not a blank line to pad."""
        gfm = "- item\n\n    ``` text\n    a\n  \n    b\n    ```\n"
        assert indent_fenced_blank_lines(gfm) == gfm

    def test_tilde_fences_are_recognized(self) -> None:
        """A tilde fence's blank lines are padded like a backtick fence's."""
        gfm = "- item\n\n    ~~~ text\n    a\n\n    b\n    ~~~\n"
        expected = "- item\n\n    ~~~ text\n    a\n    \n    b\n    ~~~\n"
        assert indent_fenced_blank_lines(gfm) == expected

    def test_shorter_marker_inside_the_fence_does_not_close_it(self) -> None:
        """A fence-like content line with a shorter marker is code, not a closing fence."""
        gfm = "- item\n\n    ```` md\n    ``` inner\n\n    ```\n    ````\n\nafter\n"
        expected = "- item\n\n    ```` md\n    ``` inner\n    \n    ```\n    ````\n\nafter\n"
        assert indent_fenced_blank_lines(gfm) == expected

    def test_state_resets_after_the_closing_fence(self) -> None:
        """A second fence gets its own indentation, independent of the first."""
        gfm = "- a\n\n    ``` x\n\n    ```\n\n- b\n\n      ``` y\n\n      ```\n"
        expected = "- a\n\n    ``` x\n    \n    ```\n\n- b\n\n      ``` y\n      \n      ```\n"
        assert indent_fenced_blank_lines(gfm) == expected
