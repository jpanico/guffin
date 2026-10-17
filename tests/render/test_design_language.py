"""Tests for guffin.render.design_language (the visual design language's tokens)."""

import importlib.resources
from pathlib import Path
from typing import Final

import pytest
import regex

from guffin.render.design_language import (
    FAMILY_PALETTE,
    TABLE_THEME,
    ColorFamily,
    DesignFamily,
    TableTheme,
    table_css,
    typst_table_tokens,
)

HEX_RE: Final[regex.Pattern[str]] = regex.compile(r"#[0-9A-Fa-f]{6}")


class TestPalette:
    """FAMILY_PALETTE is the single source of the language's colours and must cover every family."""

    def test_covers_every_family(self) -> None:
        """Every DesignFamily member has its colours (no family falls through)."""
        assert set(FAMILY_PALETTE) == set(DesignFamily)

    def test_every_family_has_a_meaning(self) -> None:
        """Each family names the kind of thing it stands for."""
        for family in DesignFamily:
            assert family.meaning

    def test_members_are_hex_colours(self) -> None:
        """A malformed colour is rejected at construction."""
        with pytest.raises(ValueError):
            ColorFamily(fill="EDF2FA", stroke="#C8D5EA", emphasis="#AFC0DC", ink="#234279")

    def test_members_step_from_light_to_dark(self) -> None:
        """Fill, stroke, emphasis, and ink step from light to dark: a background, two outlines, and text."""
        for colors in FAMILY_PALETTE.values():
            assert (
                _luminance(colors.fill)
                > _luminance(colors.stroke)
                > _luminance(colors.emphasis)
                > _luminance(colors.ink)
            )


class TestTableTheme:
    """A table is a card of one family, so its colours are that family's."""

    def test_default_table_is_a_blue_card(self) -> None:
        """The table in force is the blue family's, the processor's hue."""
        assert TABLE_THEME.family is DesignFamily.BLUE
        assert TABLE_THEME.colors == FAMILY_PALETTE[DesignFamily.BLUE]

    def test_frame_is_the_emphasis_stroke(self) -> None:
        """The frame takes the family's heavier emphasis stroke, not its hairline."""
        assert TABLE_THEME.frame_color == FAMILY_PALETTE[DesignFamily.BLUE].emphasis

    def test_any_family_can_frame_a_table(self) -> None:
        """Every family has an emphasis stroke, so a table can be a card of any of them."""
        for family in DesignFamily:
            assert TableTheme(family=family).frame_color == FAMILY_PALETTE[family].emphasis


class TestTableCss:
    """table_css expresses the table theme as stylesheet rules."""

    def test_uses_the_family_colours(self) -> None:
        """The frame, header fill, header ink, and row rule are the blue family's members."""
        css: Final[str] = table_css()
        blue: Final[ColorFamily] = FAMILY_PALETTE[DesignFamily.BLUE]
        assert f"border: {TABLE_THEME.frame_width_em}em solid {blue.emphasis}" in css
        assert f"background-color: {blue.fill}" in css
        assert f"color: {blue.ink}" in css
        assert f"border-top: {TABLE_THEME.rule_width_em}em solid {blue.stroke}" in css

    def test_rounds_the_frame_and_the_header_corners(self) -> None:
        """The table and its two top corner cells share the card radius."""
        css: Final[str] = table_css()
        radius: Final[str] = f"{TABLE_THEME.radius_em}em"
        assert f"border-radius: {radius}" in css
        assert f"thead th:first-child {{ border-top-left-radius: {radius}; }}" in css
        assert f"thead th:last-child {{ border-top-right-radius: {radius}; }}" in css

    def test_no_colour_outside_the_family(self) -> None:
        """Every colour in the rules is a member of the table's family."""
        family_colors: Final[set[str]] = {c.lower() for c in TABLE_THEME.colors.model_dump().values()}
        assert {m.lower() for m in HEX_RE.findall(table_css())} <= family_colors


class TestTypstTableTokens:
    """typst_table_tokens expresses the table theme as the template's cfg entries."""

    def test_is_a_dictionary_literal_of_the_table_keys(self) -> None:
        """Every table key the template reads is set, in one parenthesised literal."""
        tokens: Final[str] = typst_table_tokens()
        assert tokens.startswith("(")
        assert tokens.endswith(")")
        for key in (
            "table-header-bg",
            "table-header-ink",
            "table-header-weight",
            "table-striped-bg",
            "table-stroke-border-x",
            "table-stroke-border-y",
            "table-stroke-header-b",
            "table-stroke-vertical",
            "table-stroke-horizontal",
            "table-frame-stroke",
            "table-radius",
            "table-inset",
        ):
            assert f"{key}: " in tokens

    def test_frame_and_header_rule_share_the_emphasis_stroke(self) -> None:
        """The frame and the rule under the header are one stroke, the family's emphasis."""
        tokens: Final[str] = typst_table_tokens()
        frame: Final[str] = f'{TABLE_THEME.frame_width_em}em + rgb("{TABLE_THEME.frame_color}")'
        assert f"table-frame-stroke: {frame}" in tokens
        assert f"table-stroke-header-b: {frame}" in tokens

    def test_cell_borders_and_verticals_are_none(self) -> None:
        """The frame draws the outline, and columns are parted by space."""
        tokens: Final[str] = typst_table_tokens()
        for key in ("table-stroke-border-x", "table-stroke-border-y", "table-stroke-vertical"):
            assert f"{key}: none" in tokens


class TestSingleSource:
    """No format's bundled resources carry the language's colours themselves."""

    @pytest.mark.parametrize(
        ("package", "filename"),
        [
            ("guffin.render.typst_resources", "user_cfg.typ"),
            ("guffin.render.typst_resources", "base_cfg.typ"),
            ("guffin.render.epub_resources", "epub.css"),
        ],
    )
    def test_resource_carries_no_family_colour(self, package: str, filename: str) -> None:
        """A family colour written into a resource would be a second declaration of it."""
        with importlib.resources.as_file(importlib.resources.files(package) / filename) as path:
            text: Final[str] = Path(path).read_text(encoding="utf-8")
        family_colors: Final[set[str]] = {
            member.lower() for colors in FAMILY_PALETTE.values() for member in colors.model_dump().values()
        }
        assert {m.lower() for m in HEX_RE.findall(text)}.isdisjoint(family_colors)


def _luminance(hex_color: str) -> float:
    """Return a colour's relative luminance, enough to order a family's members."""
    red, green, blue = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
