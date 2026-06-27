"""Tests for guffin.render.project — project profiles and their structural policies."""

from typing import Final

from guffin.render.project import (
    BookProfile,
    DefaultProfile,
    Division,
    ManuscriptProfile,
    ProjectType,
)


class TestStructuralPolicy:
    """The structural policy each project type resolves to."""

    def test_default_is_article_like(self) -> None:
        """Default: sections, no title page, unnumbered, no abstract."""
        policy: Final = DefaultProfile().structural_policy
        assert policy.top_level_division is Division.SECTION
        assert not policy.emit_title_page
        assert not policy.number_sections
        assert not policy.emit_abstract

    def test_book_uses_chapters(self) -> None:
        """Book: chapters, title page, numbered."""
        policy: Final = BookProfile().structural_policy
        assert policy.top_level_division is Division.CHAPTER
        assert policy.emit_title_page
        assert policy.number_sections

    def test_book_with_parts_promotes_top_level(self) -> None:
        """A book with parts makes the top-level division a part."""
        policy: Final = BookProfile(with_parts=True).structural_policy
        assert policy.top_level_division is Division.PART

    def test_manuscript_emits_abstract(self) -> None:
        """Manuscript: sections, title block, unnumbered, abstract."""
        policy: Final = ManuscriptProfile().structural_policy
        assert policy.top_level_division is Division.SECTION
        assert policy.emit_abstract
        assert not policy.number_sections


class TestProfileDiscriminator:
    """Each subclass carries its own project_type discriminator and shared metadata."""

    def test_discriminators(self) -> None:
        """Each profile subclass reports its own project_type."""
        assert DefaultProfile().project_type is ProjectType.DEFAULT
        assert BookProfile().project_type is ProjectType.BOOK
        assert ManuscriptProfile().project_type is ProjectType.MANUSCRIPT

    def test_shared_metadata_fields(self) -> None:
        """Bibliographic metadata lives on the base and is carried by every subclass."""
        profile: Final = BookProfile(title="My Book", authors=("Ada", "Babbage"), identifier="ISBN-1")
        assert profile.title == "My Book"
        assert profile.authors == ("Ada", "Babbage")
        assert profile.identifier == "ISBN-1"
        assert profile.date is None
