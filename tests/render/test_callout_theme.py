"""Tests for guffin.render.callout_theme (the callout look, built on the design language)."""

from typing import Final

import regex

from guffin.render.callout_theme import CALLOUT_FAMILY, callout_colors, callout_css, typst_callout_tokens
from guffin.render.design_language import CALLOUT_THEME, FAMILY_PALETTE, DesignFamily
from guffin.roam.blockquote import CalloutType

HEX_RE: Final[regex.Pattern[str]] = regex.compile(r"#[0-9A-Fa-f]{6}")


class TestCalloutFamily:
    """CALLOUT_FAMILY is the single declaration of each callout type's family and must cover every type."""

    def test_covers_every_callout_type(self) -> None:
        """Every CalloutType member is a card of some family (no type falls through)."""
        assert set(CALLOUT_FAMILY) == set(CalloutType)

    def test_note_is_neutral(self) -> None:
        """A note is the neutral family: a note is not an alarm."""
        assert CALLOUT_FAMILY[CalloutType.NOTE] is DesignFamily.NEUTRAL

    def test_red_is_reserved_for_danger_failure_and_bug(self) -> None:
        """Exactly the alarms are red."""
        red: Final[set[CalloutType]] = {t for t, family in CALLOUT_FAMILY.items() if family is DesignFamily.RED}
        assert red == {CalloutType.DANGER, CalloutType.FAILURE, CalloutType.BUG}

    def test_colors_are_the_family_palette(self) -> None:
        """A type's colours are its family's entry in the palette, not a copy."""
        for callout_type, family in CALLOUT_FAMILY.items():
            assert callout_colors(callout_type) == FAMILY_PALETTE[family]


class TestCalloutCss:
    """callout_css expresses the callout theme as stylesheet rules."""

    def test_frames_and_rounds_the_box(self) -> None:
        """The box's own border is the frame, on the card radius, and the band rounds its top corners."""
        css: Final[str] = callout_css()
        radius: Final[str] = f"{CALLOUT_THEME.radius_em}em"
        assert f"border: {CALLOUT_THEME.frame_width_em}em solid;" in css
        assert f"border-radius: {radius};" in css
        assert f"border-top-left-radius: {radius};" in css

    def test_one_colour_rule_pair_per_type(self) -> None:
        """Each type's box takes its family's emphasis as frame and its fill and ink on the band."""
        css: Final[str] = callout_css()
        for callout_type in CalloutType:
            colors = callout_colors(callout_type)
            selector: str = f"div.callout-{callout_type.value.lower()}"
            assert f"{selector} {{ border-color: {colors.emphasis}; }}" in css
            assert f"{selector} > div.callout-title {{ background-color: {colors.fill}; color: {colors.ink};" in css

    def test_no_colour_outside_the_palette(self) -> None:
        """Every colour in the rules is a member of some family."""
        palette: Final[set[str]] = {
            member.lower() for colors in FAMILY_PALETTE.values() for member in colors.model_dump().values()
        }
        assert {m.lower() for m in HEX_RE.findall(callout_css())} <= palette


class TestTypstCalloutTokens:
    """typst_callout_tokens expresses the callout theme as the template's cfg entries."""

    def test_sets_the_measures(self) -> None:
        """The radius, frame width, insets, title weight, and icon size are all set."""
        tokens: Final[str] = typst_callout_tokens()
        assert f"callout-radius: {CALLOUT_THEME.radius_em}em" in tokens
        assert f"callout-frame-width: {CALLOUT_THEME.frame_width_em}em" in tokens
        assert "callout-header-inset: (x: " in tokens
        assert "callout-body-inset: (x: " in tokens
        assert f"callout-title-weight: {CALLOUT_THEME.title_weight}" in tokens
        assert f"callout-icon-size: {CALLOUT_THEME.icon_size_em}em" in tokens

    def test_colours_per_kind(self) -> None:
        """callout-colors holds every kind's fill, frame, and ink from its family."""
        tokens: Final[str] = typst_callout_tokens()
        for callout_type in CalloutType:
            colors = callout_colors(callout_type)
            kind: str = callout_type.value.lower()
            assert (
                f'{kind}: (fill: rgb("{colors.fill}"), frame: rgb("{colors.emphasis}"), ink: rgb("{colors.ink}"))'
                in tokens
            )
