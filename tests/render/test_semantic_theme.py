"""Tests for guffin.render.semantic_theme."""

from guffin.model.vertex_view import Semantic, SourceChannel
from guffin.render.semantic_theme import (
    BADGE_GLYPH_BY_SOURCE_CHANNEL,
    BULLET_GLYPH_BY_SEMANTIC,
    DEFAULT_BULLET_GLYPH,
)


class TestBulletGlyphBySemantic:
    """The Semantic → bullet-glyph declaration."""

    def test_covers_every_member(self) -> None:
        """Every Semantic has a bullet glyph."""
        assert set(BULLET_GLYPH_BY_SEMANTIC) == set(Semantic)

    def test_glyphs_are_single_characters(self) -> None:
        """Each bullet glyph is a single character, sized to stand where a marker was."""
        assert all(len(glyph) == 1 for glyph in BULLET_GLYPH_BY_SEMANTIC.values())


class TestBadgeGlyphBySourceChannel:
    """The SourceChannel → badge-glyph declaration."""

    def test_covers_every_member(self) -> None:
        """Every SourceChannel has a badge glyph."""
        assert set(BADGE_GLYPH_BY_SOURCE_CHANNEL) == set(SourceChannel)

    def test_glyphs_are_single_characters(self) -> None:
        """Each badge glyph is a single character."""
        assert all(len(glyph) == 1 for glyph in BADGE_GLYPH_BY_SOURCE_CHANNEL.values())


class TestDefaultBulletGlyph:
    """The plain-item glyph used alongside classified siblings."""

    def test_is_a_single_character(self) -> None:
        """The default bullet glyph is a single character."""
        assert len(DEFAULT_BULLET_GLYPH) == 1

    def test_is_not_a_semantic_glyph(self) -> None:
        """The default glyph is distinct from every semantic bullet glyph."""
        assert DEFAULT_BULLET_GLYPH not in BULLET_GLYPH_BY_SEMANTIC.values()
