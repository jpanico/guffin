"""Tests for guffin.render.project — project profiles and their structural policies."""

from typing import Final

from guffin.render.project import (
    BookProfile,
    DefaultProfile,
    ManuscriptProfile,
    ProjectProfile,
    ProjectType,
    TopLevelDivision,
    profile_for,
)


class TestProjectType:
    """ProjectType members carry both a string value and a description, behaving as a StrEnum."""

    def test_values_are_preserved(self) -> None:
        """The string value (discriminator / CLI choice / filename segment) is the bare type name."""
        assert ProjectType.DEFAULT.value == "default"
        assert ProjectType.BOOK.value == "book"
        assert ProjectType.MANUSCRIPT.value == "manuscript"
        # StrEnum identity: value-based lookup and string comparison still work.
        assert ProjectType("book") is ProjectType.BOOK
        assert ProjectType.MANUSCRIPT == "manuscript"

    def test_descriptions(self) -> None:
        """Each member exposes its one-line description."""
        assert ProjectType.DEFAULT.description == "an article-like single document"
        assert ProjectType.BOOK.description == "a multi-chapter book"
        assert ProjectType.MANUSCRIPT.description == "a scholarly paper"


class TestStructuralPolicy:
    """The structural policy each project type resolves to."""

    def test_default_is_article_like(self) -> None:
        """Default: sections, no title page, no ToC, unnumbered, no abstract, preamble kept, breaks honored."""
        policy: Final = DefaultProfile().structural_policy
        assert policy.top_level_division is TopLevelDivision.SECTION
        assert not policy.emit_title_page
        assert not policy.emit_toc
        assert not policy.number_sections
        assert not policy.emit_abstract
        assert not policy.drop_preamble
        assert policy.honor_page_breaks

    def test_book_uses_chapters(self) -> None:
        """Book: chapters, title page, generated ToC, numbered, preamble dropped, breaks fixed."""
        policy: Final = BookProfile().structural_policy
        assert policy.top_level_division is TopLevelDivision.CHAPTER
        assert policy.emit_title_page
        assert policy.emit_toc
        assert policy.number_sections
        assert policy.drop_preamble
        assert not policy.honor_page_breaks

    def test_book_with_parts_promotes_top_level(self) -> None:
        """A book with parts makes the top-level division a part."""
        policy: Final = BookProfile(with_parts=True).structural_policy
        assert policy.top_level_division is TopLevelDivision.PART

    def test_manuscript_emits_abstract(self) -> None:
        """Manuscript: sections, title block, no ToC, unnumbered, abstract, preamble kept, breaks honored."""
        policy: Final = ManuscriptProfile().structural_policy
        assert policy.top_level_division is TopLevelDivision.SECTION
        assert policy.emit_abstract
        assert not policy.emit_toc
        assert not policy.number_sections
        assert not policy.drop_preamble
        assert policy.honor_page_breaks


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


class TestProfileFor:
    """profile_for maps a project type to its default-valued profile subclass."""

    def test_maps_each_type_to_its_subclass(self) -> None:
        """Each ProjectType yields the matching profile subclass."""
        assert isinstance(profile_for(ProjectType.DEFAULT), DefaultProfile)
        assert isinstance(profile_for(ProjectType.BOOK), BookProfile)
        assert isinstance(profile_for(ProjectType.MANUSCRIPT), ManuscriptProfile)

    def test_returned_subtype_survives_validate_call(self) -> None:
        """A subclass passed where the base is annotated keeps its concrete type and policy.

        Guards the renderers' ``profile: ProjectProfile`` parameters: pydantic ``@validate_call``
        must not coerce a ``BookProfile`` down to the base and lose its structural policy.
        """
        from pydantic import validate_call

        @validate_call
        def accept(profile: ProjectProfile) -> ProjectProfile:
            return profile

        result: Final = accept(profile_for(ProjectType.BOOK))
        assert isinstance(result, BookProfile)
        assert result.structural_policy.top_level_division is TopLevelDivision.CHAPTER
