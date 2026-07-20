"""Tests for guffin.common.whitespace."""

from guffin.common.whitespace import normalize_spaces

_NBSP = " "  # NO-BREAK SPACE
_NARROW_NBSP = " "  # NARROW NO-BREAK SPACE
_EM_SPACE = " "  # EM SPACE
_THIN_SPACE = " "  # THIN SPACE
_IDEOGRAPHIC_SPACE = "　"  # IDEOGRAPHIC SPACE
_OGHAM_SPACE = " "  # OGHAM SPACE MARK
_ZWJ = "‍"  # ZERO WIDTH JOINER (category Cf, not Zs)


class TestNormalizeSpaces:
    """normalize_spaces folds non-ASCII Unicode space separators to the ASCII space."""

    def test_no_break_space_becomes_ascii_space(self) -> None:
        """A no-break space (U+00A0) is replaced by an ordinary space."""
        assert normalize_spaces(f"A{_NBSP}B") == "A B"

    def test_every_word_separator_folded(self) -> None:
        """A line authored entirely with no-break spaces becomes ordinary, breakable text."""
        source = _NBSP.join(["A", "Rube", "Goldberg", "machine"])
        assert normalize_spaces(source) == "A Rube Goldberg machine"

    def test_covers_the_whole_zs_category(self) -> None:
        """Narrow NBSP, fixed-width, ideographic, and Ogham spaces all fold to the ASCII space."""
        source = f"a{_NARROW_NBSP}b{_EM_SPACE}c{_THIN_SPACE}d{_IDEOGRAPHIC_SPACE}e{_OGHAM_SPACE}f"
        assert normalize_spaces(source) == "a b c d e f"

    def test_ascii_space_unchanged(self) -> None:
        """An ordinary ASCII space is left exactly as-is (never doubled or collapsed)."""
        assert normalize_spaces("a b  c") == "a b  c"

    def test_length_preserving_never_collapses_runs(self) -> None:
        """Consecutive separators map one-for-one; runs are preserved, not collapsed."""
        assert normalize_spaces(f"a{_NBSP}{_NBSP}b") == "a  b"

    def test_tabs_and_newlines_untouched(self) -> None:
        """Non-Zs whitespace (tab, newline) is structural and left unchanged."""
        assert normalize_spaces("a\tb\nc") == "a\tb\nc"

    def test_zero_width_joiner_untouched(self) -> None:
        """A zero-width joiner (category Cf, not Zs) is preserved — e.g. emoji sequences."""
        family = f"\U0001f468{_ZWJ}\U0001f469{_ZWJ}\U0001f467"
        assert normalize_spaces(family) == family

    def test_plain_text_unchanged(self) -> None:
        """Text with no exotic separators passes through untouched."""
        assert normalize_spaces("nothing exotic here") == "nothing exotic here"

    def test_empty_string(self) -> None:
        """The empty string normalizes to itself."""
        assert normalize_spaces("") == ""
