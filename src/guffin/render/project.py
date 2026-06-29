"""Project profile: the *kind* of work being rendered, modeled on Quarto's ``project: type:``.

This adopts Quarto's project-type *concept* — not any Quarto artifact: no ``_quarto.yml``, no
``quarto`` CLI, no extensions.  Just a native vocabulary (``default`` / ``book`` / ``manuscript``)
and the structural semantics each implies, expressed as Guffin's own Pydantic models.

The project profile is orthogonal to the output format
(:class:`~guffin.render.render_options.RenderOptions`): the profile says *what kind of work* the
content is, the format says *how/where* to render it.  A profile resolves to a format-independent
:class:`StructuralPolicy` (top-level division, title page, numbering, abstract) that each renderer
maps onto its own mechanism (PDF document class / EPUB split level / etc.).

Public symbols:

- **Enumerations**: :class:`ProjectType` — the supported project types (default / book / manuscript);
  :class:`TopLevelDivision` — the top-level structural division a project's highest headings
  represent.
- **Models**: :class:`StructuralPolicy` — the format-independent structural directives derived from a
  profile; :class:`ProjectProfile` — the format-independent base profile; and the per-type subclasses
  :class:`DefaultProfile`, :class:`BookProfile`, :class:`ManuscriptProfile`.
- **Functions**: :func:`profile_for` — build a default-valued :class:`ProjectProfile` for a
  :class:`ProjectType`.
"""

import enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, validate_call


class ProjectType(enum.StrEnum):
    """The kind of work a render produces, used as the discriminator of the profile subclasses.

    Attributes:
        DEFAULT: A flowing, article-like single document (:class:`DefaultProfile`).
        BOOK: A multi-chapter book (:class:`BookProfile`).
        MANUSCRIPT: A scholarly article/paper (:class:`ManuscriptProfile`).
    """

    DEFAULT = "default"
    BOOK = "book"
    MANUSCRIPT = "manuscript"


class TopLevelDivision(enum.StrEnum):
    """The structural division a project's top-level (level-1) headings represent.

    Mirrors Pandoc's ``--top-level-division`` rungs; each renderer maps it onto its own
    mechanism (e.g. PDF document class, EPUB content split).

    Attributes:
        SECTION: Top-level headings are sections (the article model).
        CHAPTER: Top-level headings are chapters (the book/report model).
        PART: Top-level headings are parts (the largest grouping).
    """

    SECTION = "section"
    CHAPTER = "chapter"
    PART = "part"


class StructuralPolicy(BaseModel):
    """Format-independent structural directives derived from a :class:`ProjectProfile`.

    A renderer consumes this rather than branching on :class:`ProjectType` directly, so the
    type-to-structure semantics live in one place.

    Attributes:
        top_level_division: What a level-1 heading becomes (section / chapter / part).
        emit_title_page: Whether to render a standalone title page (and a table of contents).
        number_sections: Whether divisions are numbered.
        emit_abstract: Whether to render an abstract block from the profile.
    """

    model_config = ConfigDict(frozen=True)

    top_level_division: TopLevelDivision = Field(..., description="What a level-1 heading becomes.")
    emit_title_page: bool = Field(..., description="Render a standalone title page (and TOC).")
    number_sections: bool = Field(..., description="Number the divisions.")
    emit_abstract: bool = Field(..., description="Render an abstract block from the profile.")


class ProjectProfile(BaseModel):
    """The format-independent description of the work being rendered.

    A base for the per-type subclasses (:class:`DefaultProfile`, :class:`BookProfile`,
    :class:`ManuscriptProfile`); not instantiated directly.  Carries bibliographic metadata that
    every output format can consume (e.g. PDF title block, EPUB ``dc:*``); ``None``/empty values
    fall back to what the content itself provides (such as the page title).

    Attributes:
        title: Publication title; ``None`` uses the root page's own title.
        authors: Author names, in byline order.
        date: Publication date (ISO-8601 recommended); ``None`` lets the renderer decide.
        identifier: A stable identifier for the work (e.g. ISBN, DOI), if any.
    """

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, description="Publication title; None uses the page title.")
    authors: tuple[str, ...] = Field(default=(), description="Author names, in byline order.")
    date: str | None = Field(default=None, description="Publication date (ISO-8601 recommended).")
    identifier: str | None = Field(default=None, description="Stable work identifier (ISBN, DOI, …).")

    @property
    def structural_policy(self) -> StructuralPolicy:
        """Return the :class:`StructuralPolicy` this profile resolves to."""
        raise NotImplementedError


class DefaultProfile(ProjectProfile):
    """An article-like single document — the default project type.

    Attributes:
        project_type: Always :attr:`ProjectType.DEFAULT` (the discriminator).
    """

    project_type: Literal[ProjectType.DEFAULT] = Field(
        default=ProjectType.DEFAULT, description="Discriminator identifying a default (article) project."
    )

    @property
    def structural_policy(self) -> StructuralPolicy:
        """Sections, no title page, unnumbered, no abstract."""
        return StructuralPolicy(
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=False,
            number_sections=False,
            emit_abstract=False,
        )


class BookProfile(ProjectProfile):
    """A multi-chapter book: top-level headings are chapters.

    Attributes:
        project_type: Always :attr:`ProjectType.BOOK` (the discriminator).
        with_parts: When ``True``, level-1 headings are parts and level-2 headings are chapters;
            when ``False`` (default), level-1 headings are chapters.
    """

    project_type: Literal[ProjectType.BOOK] = Field(
        default=ProjectType.BOOK, description="Discriminator identifying a book project."
    )
    with_parts: bool = Field(default=False, description="Top-level headings are parts (else chapters).")

    @property
    def structural_policy(self) -> StructuralPolicy:
        """Chapters (or parts), a title page + TOC, numbered, no abstract."""
        return StructuralPolicy(
            top_level_division=TopLevelDivision.PART if self.with_parts else TopLevelDivision.CHAPTER,
            emit_title_page=True,
            number_sections=True,
            emit_abstract=False,
        )


class ManuscriptProfile(ProjectProfile):
    """A scholarly article/paper.

    Attributes:
        project_type: Always :attr:`ProjectType.MANUSCRIPT` (the discriminator).
        abstract: Optional abstract text rendered ahead of the body.
        keywords: Optional keyword list associated with the manuscript.
    """

    project_type: Literal[ProjectType.MANUSCRIPT] = Field(
        default=ProjectType.MANUSCRIPT, description="Discriminator identifying a manuscript project."
    )
    abstract: str | None = Field(default=None, description="Abstract text rendered ahead of the body.")
    keywords: tuple[str, ...] = Field(default=(), description="Keywords associated with the manuscript.")

    @property
    def structural_policy(self) -> StructuralPolicy:
        """Sections, a title block, unnumbered, with an abstract."""
        return StructuralPolicy(
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=True,
            number_sections=False,
            emit_abstract=True,
        )


@validate_call
def profile_for(project_type: ProjectType) -> ProjectProfile:
    """Return a default-valued :class:`ProjectProfile` of the given *project_type*.

    Maps each :class:`ProjectType` to its corresponding profile subclass, constructed with default
    (empty) bibliographic metadata.  Front ends use this to turn a selected project type into a
    profile to pass to a renderer.

    Args:
        project_type: The kind of work to build a profile for.

    Returns:
        A :class:`DefaultProfile`, :class:`BookProfile`, or :class:`ManuscriptProfile`.
    """
    match project_type:
        case ProjectType.DEFAULT:
            return DefaultProfile()
        case ProjectType.BOOK:
            return BookProfile()
        case ProjectType.MANUSCRIPT:
            return ManuscriptProfile()
