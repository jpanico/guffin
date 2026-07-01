"""Guffin's own attribute vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Enumerations**: :class:`GuffinSemantics` — the attributes Guffin recognizes (document metadata +
  the ``element-type`` heading tag), each member a :class:`GuffinAttribute` in the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`
  domain; :class:`Anchor` — the kind of vertex a Guffin attribute attaches to (page / heading), each
  carrying its :class:`~guffin.model.vertex_type.VertexType`; :class:`Matter` —
  the book division a part belongs to (front / body / back); :class:`StructuralElement` — a book's
  structural elements by name, each carrying its :class:`Matter` division (its organizational parts).
- **Models**: :class:`GuffinAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`Anchor`.
- **Functions**: :func:`element_type_of` — read an ``element-type`` assignment's value as a
  :class:`StructuralElement` (raising if it is not one).
"""

import enum
from typing import Final, Self

from pydantic import Field, field_validator, validate_call

from guffin.model.attribute import Attribute, AttributeAssignment, AttributeDomain, sole_value_text
from guffin.model.vertex_type import VertexType


class Anchor(enum.StrEnum):
    """The kind of vertex a Guffin attribute attaches to.

    Each member carries the :class:`~guffin.model.vertex_type.VertexType` it corresponds to — the type
    of vertex an attribute with this anchor may be declared on.

    Attributes:
        vertex_type: The :class:`~guffin.model.vertex_type.VertexType` this anchor corresponds to.
        PAGE: The attribute attaches to a page vertex (the whole document).
        HEADING: The attribute attaches to a heading vertex (a section).
    """

    def __new__(cls, value: str, vertex_type: VertexType) -> Self:
        """Create a member whose string value is *value* and that carries *vertex_type*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.vertex_type = vertex_type
        return member

    vertex_type: VertexType

    PAGE = ("page", VertexType.PAGE)
    HEADING = ("heading", VertexType.HEADING)


class Matter(enum.StrEnum):
    """A top-level division of a book — the publishing-standard grouping its parts belong to.

    Attributes:
        FRONT: Front matter — material preceding the main text (title page, foreword, preface, …).
        BODY: Body matter — the main text (parts, chapters).
        BACK: Back matter — material following the main text (appendices, glossary, colophon, …).
    """

    FRONT = "front-matter"
    BODY = "body-matter"
    BACK = "back-matter"


class GuffinAttribute(Attribute):
    """A Guffin-domain :class:`~guffin.model.attribute.Attribute` that also carries a :class:`Anchor`.

    Specializes :class:`~guffin.model.attribute.Attribute` by pinning :attr:`domain` to
    :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` (any other value is rejected) and adding a
    required :attr:`anchor`.

    Attributes:
        domain: Always :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`.
        anchor: The kind of vertex this attribute attaches to.
    """

    domain: AttributeDomain = Field(default=AttributeDomain.GUFFIN, description="Always the guffin domain.")
    anchor: Anchor = Field(..., description="The kind of vertex this attribute attaches to.")

    @field_validator("domain")
    @classmethod
    def _domain_must_be_guffin(cls, value: AttributeDomain) -> AttributeDomain:
        """Reject any domain other than :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`."""
        if value is not AttributeDomain.GUFFIN:
            raise ValueError(f"GuffinAttribute.domain is fixed to {AttributeDomain.GUFFIN!r}, got {value!r}")
        return value


class GuffinSemantics(enum.Enum):
    """The attributes Guffin recognizes, each a :class:`GuffinAttribute`.

    Each member's value is the :class:`GuffinAttribute` for that attribute.  Two kinds:

    - **Document metadata** (:attr:`Anchor.PAGE`) — bibliographic facts about the work as a whole:
      :attr:`TITLE`, :attr:`AUTHORS`, :attr:`DATE`, :attr:`IDENTIFIER`.
    - **Heading tags** (:attr:`Anchor.HEADING`) — applied to an individual heading: :attr:`ELEMENT_TYPE`
      declares which :class:`StructuralElement` the heading is.

    Attributes:
        TITLE: The document title.
        AUTHORS: The document author(s).
        DATE: The document date.
        IDENTIFIER: The document identifier.
        ELEMENT_TYPE: Tags a heading with its :class:`StructuralElement` (the book part it is).
    """

    _value_: GuffinAttribute

    TITLE = GuffinAttribute(name="title", anchor=Anchor.PAGE)
    AUTHORS = GuffinAttribute(name="authors", anchor=Anchor.PAGE)
    DATE = GuffinAttribute(name="date", anchor=Anchor.PAGE)
    IDENTIFIER = GuffinAttribute(name="identifier", anchor=Anchor.PAGE)
    ELEMENT_TYPE = GuffinAttribute(name="element-type", anchor=Anchor.HEADING)


class StructuralElement(enum.StrEnum):
    """The structural elements of a book — its organizational parts, each in a :class:`Matter` division.

    The reusable section types an author tags a heading with, from :attr:`COVER` through
    :attr:`COLOPHON` — title page, foreword, preface, parts and chapters, appendices, glossary, index,
    colophon, and so on.  Member names follow publishing conventions; each member's value is that name,
    and :attr:`matter` is the front/body/back-matter division it conventionally belongs to.

    Attributes:
        matter: The :class:`Matter` division this element belongs to.
    """

    def __new__(cls, value: str, matter: Matter) -> Self:
        """Create a member whose string value is *value* and that carries *matter*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.matter = matter
        return member

    matter: Matter

    COVER = ("cover", Matter.FRONT)
    TITLE_PAGE = ("title-page", Matter.FRONT)
    COPYRIGHT_PAGE = ("copyright-page", Matter.FRONT)
    EPIGRAPH = ("epigraph", Matter.FRONT)
    ACKNOWLEDGEMENTS = ("acknowledgements", Matter.FRONT)
    FOREWORD = ("foreword", Matter.FRONT)
    PREFACE = ("preface", Matter.FRONT)
    INTRODUCTION = ("introduction", Matter.FRONT)
    TABLE_OF_CONTENTS = ("table-of-contents", Matter.FRONT)
    LIST_OF_ILLUSTRATIONS = ("list-of-illustrations", Matter.FRONT)
    PART = ("part", Matter.BODY)
    CHAPTER = ("chapter", Matter.BODY)
    SECTION = ("section", Matter.BODY)
    SUB_SECTION = ("sub-section", Matter.BODY)
    SUB_SUB_SECTION = ("sub-sub-section", Matter.BODY)
    CONCLUSION = ("conclusion", Matter.BACK)
    EPILOGUE = ("epilogue", Matter.BACK)
    AFTERWORD = ("afterword", Matter.BACK)
    APPENDICES = ("appendices", Matter.BACK)
    GLOSSARY = ("glossary", Matter.BACK)
    ENDNOTES = ("endnotes", Matter.BACK)
    BIBLIOGRAPHY = ("bibliography", Matter.BACK)
    INDEX = ("index", Matter.BACK)
    ABOUT_THE_AUTHOR = ("about-the-author", Matter.BACK)
    COLOPHON = ("colophon", Matter.BACK)


@validate_call
def element_type_of(assignment: AttributeAssignment) -> StructuralElement:
    """Return the :class:`StructuralElement` that an ``element-type`` assignment names.

    Verifies *assignment* is for the :attr:`GuffinSemantics.ELEMENT_TYPE` attribute, then coerces its
    sole value to a :class:`StructuralElement` — the authoritative set of legal ``element-type`` values.

    Args:
        assignment: An :attr:`GuffinSemantics.ELEMENT_TYPE` attribute assignment (one value expected).

    Returns:
        The named :class:`StructuralElement`.

    Raises:
        ValueError: If *assignment* is not for the ``element-type`` attribute, does not carry exactly
            one value, or its value is not a recognised :class:`StructuralElement`.
    """
    element_type: Final[GuffinAttribute] = GuffinSemantics.ELEMENT_TYPE.value
    definition: Final[Attribute] = assignment.attribute.definition
    if definition.name != element_type.name or definition.domain != element_type.domain:
        raise ValueError(
            f"expected an {element_type.name!r} assignment in the {element_type.domain} domain, "
            f"got {definition.name!r} in {definition.domain}"
        )
    return StructuralElement(sole_value_text(assignment))
