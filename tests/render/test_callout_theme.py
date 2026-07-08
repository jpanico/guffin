"""Tests for guffin.render.callout_theme (the canonical callout colour palette)."""

from guffin.render.callout_theme import (
    CALLOUT_ACCENT,
    TITLE_TINT_LIGHTEN,
    callout_accent,
    callout_title_tint,
    lighten,
)
from guffin.roam.blockquote import CalloutType


class TestPalette:
    """CALLOUT_ACCENT is the single source of truth and must cover every callout type."""

    def test_covers_every_callout_type(self) -> None:
        """Every CalloutType member has a canonical accent colour (no type falls through)."""
        assert set(CALLOUT_ACCENT) == set(CalloutType)

    def test_accents_are_hex_colours(self) -> None:
        """Each accent is a ``#rrggbb`` hex string."""
        for color in CALLOUT_ACCENT.values():
            assert len(color) == 7
            assert color[0] == "#"
            int(color[1:], 16)  # raises if not hex

    def test_note_and_quote_are_neutral(self) -> None:
        """Note and quote are neutral greys (red is reserved for danger/failure/bug)."""
        for neutral in (CalloutType.NOTE, CalloutType.QUOTE):
            red, green, blue = (int(CALLOUT_ACCENT[neutral][i : i + 2], 16) for i in (1, 3, 5))
            assert red == green == blue  # grey: equal channels


class TestLighten:
    """lighten blends a colour toward white, matching Typst's color.lighten."""

    def test_zero_amount_is_unchanged(self) -> None:
        """Lightening by 0 returns the same colour."""
        assert lighten("#4a90d9", 0.0) == "#4a90d9"

    def test_full_amount_is_white(self) -> None:
        """Lightening by 1 returns white regardless of input."""
        assert lighten("#000000", 1.0) == "#ffffff"
        assert lighten("#4a90d9", 1.0) == "#ffffff"

    def test_white_stays_white(self) -> None:
        """Lightening white is a no-op at any amount."""
        assert lighten("#ffffff", 0.5) == "#ffffff"

    def test_known_midpoint(self) -> None:
        """Half-lightening #000000 yields the rounded mid-grey #808080."""
        assert lighten("#000000", 0.5) == "#808080"

    def test_accepts_bare_hex_without_hash(self) -> None:
        """A leading '#' is optional on the input."""
        assert lighten("000000", 1.0) == "#ffffff"


class TestAccessors:
    """callout_accent and callout_title_tint read the palette and derive the tint."""

    def test_accent_reads_palette(self) -> None:
        """callout_accent returns the palette entry."""
        assert callout_accent(CalloutType.INFO) == CALLOUT_ACCENT[CalloutType.INFO]

    def test_title_tint_is_lightened_accent(self) -> None:
        """The title tint is the accent lightened by TITLE_TINT_LIGHTEN."""
        assert callout_title_tint(CalloutType.NOTE) == lighten(CALLOUT_ACCENT[CalloutType.NOTE], TITLE_TINT_LIGHTEN)

    def test_grey_note_tint_matches_prior_hand_tuned_value(self) -> None:
        """The derived note tint reproduces the previously hand-tuned #ededed."""
        assert callout_title_tint(CalloutType.NOTE) == "#ededed"
