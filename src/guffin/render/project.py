"""Project profile: the *kind* of work being rendered, modeled on Quarto's ``project: type:``.

This adopts Quarto's project-type *concept* — not any Quarto artifact: no ``_quarto.yml``, no
``quarto`` CLI, no extensions.  Just a native vocabulary (``default`` / ``book`` / ``manuscript``)
and the structural semantics each implies, expressed as Guffin's own Pydantic models.

The project profile is orthogonal to the output format
(:class:`~guffin.render.render_options.RenderOptions`): the profile says *what kind of work* the
content is, the format says *how/where* to render it.  A profile resolves to a format-independent
:class:`StructuralPolicy` (top-level division, title page, numbering, abstract, preamble handling)
that each renderer maps onto its own mechanism (PDF document class / EPUB split level / etc.).

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
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, validate_call


class ProjectType(enum.StrEnum):
    """The kind of work a render produces, used as the discriminator of the profile subclasses.

    Each member pairs its string value — the profile discriminator, CLI ``--type`` choice, and
    output-filename segment — with a one-line :attr:`description` of the kind of work it produces.

    Attributes:
        description: A one-line description of the kind of work the member produces.
        DEFAULT: A flowing, article-like single document (:class:`DefaultProfile`).
        BOOK: A multi-chapter book (:class:`BookProfile`).
        MANUSCRIPT: A scholarly article/paper (:class:`ManuscriptProfile`).
    """

    DEFAULT = ("default", "an article-like single document")
    BOOK = ("book", "a multi-chapter book")
    MANUSCRIPT = ("manuscript", "a scholarly paper")

    description: str

    def __new__(cls, value: str, description: str) -> Self:
        """Create a member whose string value is *value* and that carries *description*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.description = description
        return member


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

    Each directive is a statement about the *work* ("a book presents a table of contents"), not a
    guarantee about any particular output: a consumer maps directives onto the mechanisms its
    output format offers, and that mapping is deliberately partial — a directive with no
    counterpart in a format is simply not expressed there.

    Attributes:
        top_level_division: What a level-1 heading becomes (section / chapter / part).
        emit_title_page: Whether to render a standalone title page.
        emit_toc: Whether the work presents a navigable table of contents.  How a format
            expresses it is the renderer's mapping — an outline rendered into the output, or
            a navigation structure an output format already carries.
        number_sections: Whether divisions are numbered.
        emit_abstract: Whether to render an abstract block from the profile.
        drop_preamble: Whether to drop the export root's loose preamble — children preceding its
            first heading child, content belonging to no titled division — from paginated output.
        honor_page_breaks: Whether authored ``page-break`` directives are honored.  A work whose
            pagination is fixed by its own structural conventions (a book: chapters and parts open
            pages by ritual, not by tag) does not honor them; a work whose pagination is the
            author's to shape does.
    """

    model_config = ConfigDict(frozen=True)

    top_level_division: TopLevelDivision = Field(..., description="What a level-1 heading becomes.")
    emit_title_page: bool = Field(..., description="Render a standalone title page.")
    emit_toc: bool = Field(..., description="The work presents a navigable table of contents.")
    number_sections: bool = Field(..., description="Number the divisions.")
    emit_abstract: bool = Field(..., description="Render an abstract block from the profile.")
    drop_preamble: bool = Field(..., description="Drop the root's children preceding its first heading.")
    honor_page_breaks: bool = Field(..., description="Honor authored page-break directives.")


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
        """Sections, no title page, no generated ToC, unnumbered, no abstract, preamble kept, page breaks honored."""
        return StructuralPolicy(
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=False,
            emit_toc=False,
            number_sections=False,
            emit_abstract=False,
            drop_preamble=False,
            honor_page_breaks=True,
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
        """Chapters (or parts), a title page, a generated ToC, numbered, no abstract, preamble dropped, page breaks.

        fixed.

        A book's root is a container for its divisions: loose preamble ahead of the first
        chapter belongs to no division (and would otherwise surface as a spurious title-bearing
        chapter in paginated output), so it is dropped by default.  A book's pagination is
        likewise fixed by its structure — chapters and parts open pages by convention — so
        authored ``page-break`` directives are not honored.
        """
        return StructuralPolicy(
            top_level_division=TopLevelDivision.PART if self.with_parts else TopLevelDivision.CHAPTER,
            emit_title_page=True,
            emit_toc=True,
            number_sections=True,
            emit_abstract=False,
            drop_preamble=True,
            honor_page_breaks=False,
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
        """Sections, a title block, no generated ToC, unnumbered, with an abstract, preamble kept, page breaks.

        honored.
        """
        return StructuralPolicy(
            top_level_division=TopLevelDivision.SECTION,
            emit_title_page=True,
            emit_toc=False,
            number_sections=False,
            emit_abstract=True,
            drop_preamble=False,
            honor_page_breaks=True,
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
