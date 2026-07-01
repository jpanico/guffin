"""Guffin's own attribute vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Enumerations**: :class:`GuffinSemantics` — the attributes Guffin recognizes, each member a
  :class:`GuffinAttribute` in the :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain
  (publishing metadata + structural book-section tags);
  :class:`Role` — the role a Guffin attribute plays (publishing / structural); :class:`Level` — the
  structural level at which a Guffin attribute applies (document / header).
- **Models**: :class:`GuffinAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`Role`.
"""

import enum

from pydantic import Field, field_validator

from guffin.model.attribute import Attribute, AttributeDomain


class Role(enum.StrEnum):
    """The role a Guffin attribute plays.

    Attributes:
        PUBLISHING: A publishing role — the attribute contributes to bibliographic/output metadata.
        STRUCTURAL: A structural role — the attribute conveys structural meaning about the content.
    """

    PUBLISHING = "publishing"
    STRUCTURAL = "structural"


class Level(enum.StrEnum):
    """The structural level at which a Guffin attribute applies.

    Attributes:
        DOCUMENT: The attribute applies to the document as a whole.
        HEADER: The attribute applies to an individual header (section).
    """

    DOCUMENT = "document"
    HEADER = "header"


class GuffinAttribute(Attribute):
    """A Guffin-domain :class:`~guffin.model.attribute.Attribute` that also carries a :class:`Role` and :class:`Level`.

    Specializes :class:`~guffin.model.attribute.Attribute` by pinning :attr:`domain` to
    :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` (any other value is rejected) and adding a
    required :attr:`role` and :attr:`level`.

    Attributes:
        domain: Always :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`.
        role: The role this attribute plays.
        level: The structural level at which this attribute applies.
    """

    domain: AttributeDomain = Field(default=AttributeDomain.GUFFIN, description="Always the guffin domain.")
    role: Role = Field(..., description="The role this attribute plays.")
    level: Level = Field(..., description="The structural level at which this attribute applies.")

    @field_validator("domain")
    @classmethod
    def _domain_must_be_guffin(cls, value: AttributeDomain) -> AttributeDomain:
        """Reject any domain other than :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`."""
        if value is not AttributeDomain.GUFFIN:
            raise ValueError(f"GuffinAttribute.domain is fixed to {AttributeDomain.GUFFIN!r}, got {value!r}")
        return value


def _publishing(name: str) -> GuffinAttribute:
    """Build a publishing (:attr:`Role.PUBLISHING`, :attr:`Level.DOCUMENT`) attribute named *name*."""
    return GuffinAttribute(name=name, role=Role.PUBLISHING, level=Level.DOCUMENT)


def _structural(name: str) -> GuffinAttribute:
    """Build a structural (:attr:`Role.STRUCTURAL`, :attr:`Level.HEADER`) attribute named *name*."""
    return GuffinAttribute(name=name, role=Role.STRUCTURAL, level=Level.HEADER)


class GuffinSemantics(enum.Enum):
    """The attributes Guffin recognizes, each a :class:`GuffinAttribute` in the guffin domain.

    Each member's value is the :class:`GuffinAttribute` for that attribute — its name paired with the
    :class:`Role` and :class:`Level` it carries.  Two groups:

    - **Publishing metadata** (:attr:`Role.PUBLISHING`, :attr:`Level.DOCUMENT`) — document-level
      bibliographic facts: :attr:`TITLE`, :attr:`AUTHORS`, :attr:`DATE`, :attr:`IDENTIFIER`.
    - **Structural sections** (:attr:`Role.STRUCTURAL`, :attr:`Level.HEADER`) — book-structure tags an
      author applies to a heading, from :attr:`COVER` through :attr:`COLOPHON`.

    Attributes:
        TITLE: The document title.
        AUTHORS: The document author(s).
        DATE: The document date.
        IDENTIFIER: The document identifier.
        COVER: The book cover.
        TITLE_PAGE: The title page.
        COPYRIGHT_PAGE: The copyright page.
        EPIGRAPH: An epigraph.
        ACKNOWLEDGEMENTS: The acknowledgements.
        FOREWORD: The foreword.
        PREFACE: The preface.
        INTRODUCTION: The introduction.
        TABLE_OF_CONTENTS: The table of contents.
        PART: A part.
        CHAPTER: A chapter.
        SECTION: A section.
        SUB_SECTION: A subsection.
        SUB_SUB_SECTION: A sub-subsection.
        CONCLUSION: The conclusion.
        EPILOGUE: The epilogue.
        AFTERWORD: The afterword.
        APPENDICES: The appendices.
        GLOSSARY: The glossary.
        LIST_OF_ILLUSTRATIONS: The list of illustrations.
        ENDNOTES: The endnotes.
        BIBLIOGRAPHY: The bibliography.
        INDEX: The index.
        ABOUT_THE_AUTHOR: The "about the author" section.
        COLOPHON: The colophon.
    """

    _value_: GuffinAttribute

    # Publishing metadata (Role.PUBLISHING, Level.DOCUMENT).
    TITLE = _publishing("title")
    AUTHORS = _publishing("authors")
    DATE = _publishing("date")
    IDENTIFIER = _publishing("identifier")

    # Structural book-structure sections (Role.STRUCTURAL, Level.HEADER).
    COVER = _structural("cover")
    TITLE_PAGE = _structural("title-page")
    COPYRIGHT_PAGE = _structural("copyright-page")
    EPIGRAPH = _structural("epigraph")
    ACKNOWLEDGEMENTS = _structural("acknowledgements")
    FOREWORD = _structural("foreword")
    PREFACE = _structural("preface")
    INTRODUCTION = _structural("introduction")
    TABLE_OF_CONTENTS = _structural("table-of-contents")
    PART = _structural("part")
    CHAPTER = _structural("chapter")
    SECTION = _structural("section")
    SUB_SECTION = _structural("sub-section")
    SUB_SUB_SECTION = _structural("sub-sub-section")
    CONCLUSION = _structural("conclusion")
    EPILOGUE = _structural("epilogue")
    AFTERWORD = _structural("afterword")
    APPENDICES = _structural("appendices")
    GLOSSARY = _structural("glossary")
    LIST_OF_ILLUSTRATIONS = _structural("list-of-illustrations")
    ENDNOTES = _structural("endnotes")
    BIBLIOGRAPHY = _structural("bibliography")
    INDEX = _structural("index")
    ABOUT_THE_AUTHOR = _structural("about-the-author")
    COLOPHON = _structural("colophon")
