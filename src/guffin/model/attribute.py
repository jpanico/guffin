"""Normalized model of a Roam attribute assignment (``<attribute>:: <value>, …``).

A Roam attribute assignment names an attribute — itself a Roam *Page* — and assigns it an ordered
list of values, each of which is either a bare literal token or a reference to another page.  This
module models that construct decoupled from the Roam/parsing layer: page references are captured as
:class:`~guffin.model.link.VertexLink` pointers rather than raw Roam UIDs or strings.

Public symbols:

- **Type aliases**: :data:`AttributeValue` — discriminated union of :class:`LiteralValue` and
  :class:`ReferenceValue`.
- **Enumerations**: :class:`AttributeValueKind` — the two value kinds (literal / reference);
  :class:`GuffinAttribute` — the attributes Guffin recognizes in :data:`GUFFIN_ATTRIBUTE_DOMAIN`.
- **Models**: :class:`Attribute` — the named attribute (a page) preceding ``::``; :class:`LiteralValue`
  — a bare literal value; :class:`ReferenceValue` — a value that references a page; and
  :class:`AttributeAssignment` — an :class:`Attribute` paired with its ordered values.
- **Adapters**: :data:`attribute_value_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for
  validating a raw mapping into the appropriate :data:`AttributeValue`.
- **Constants**: :data:`DEFAULT_ATTRIBUTE_DOMAIN` — the default :attr:`Attribute.domain` value;
  :data:`GUFFIN_ATTRIBUTE_DOMAIN` — Guffin's own reserved domain.
"""

import enum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from guffin.model.link import VertexLink

DEFAULT_ATTRIBUTE_DOMAIN: Final[str] = "default"
"""The default namespace assigned to an :class:`Attribute` when no domain is specified."""

GUFFIN_ATTRIBUTE_DOMAIN: Final[str] = "guffin"
"""Guffin's own reserved :attr:`Attribute.domain` namespace."""


class GuffinAttribute(enum.StrEnum):
    """The attributes Guffin recognizes, all in the :attr:`DOMAIN` namespace.

    Each member's value is the attribute name as it appears in Roam (the page named before ``::``).
    :attr:`DOMAIN` — bound to :data:`GUFFIN_ATTRIBUTE_DOMAIN` — is the shared :attr:`Attribute.domain`
    every member belongs to; it is a class-level constant, not itself an attribute name (and so does
    not appear when iterating the enum).

    Attributes:
        DOMAIN: The shared :attr:`Attribute.domain` of every member.
        TITLE: The document title.
        AUTHORS: The document author(s).
        DATE: The document date.
        IDENTIFIER: The document identifier.
    """

    DOMAIN = enum.nonmember(GUFFIN_ATTRIBUTE_DOMAIN)

    TITLE = "title"
    AUTHORS = "authors"
    DATE = "date"
    IDENTIFIER = "identifier"


class AttributeValueKind(enum.StrEnum):
    """The kind of an attribute-assignment value, used as the discriminator of :data:`AttributeValue`.

    Attributes:
        LITERAL: A bare literal token (:class:`LiteralValue`).
        REFERENCE: A reference to a page (:class:`ReferenceValue`).
    """

    LITERAL = "literal"
    REFERENCE = "reference"


class Attribute(BaseModel):
    """The attribute of an attribute assignment — the page named before the ``::`` separator.

    Attributes:
        name: The attribute name, i.e. the title of the referenced Roam *Page*.
        link: A reference link to the page named by :attr:`name`.
        domain: The namespace the attribute belongs to; defaults to ``"default"``.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="The attribute name — the title of the referenced page.")
    link: VertexLink = Field(..., description="Reference link to the page named by `name`.")
    domain: str = Field(default=DEFAULT_ATTRIBUTE_DOMAIN, description="The namespace the attribute belongs to.")


class LiteralValue(BaseModel):
    """An attribute value that is a bare literal token rather than a page reference.

    Attributes:
        kind: Always :attr:`AttributeValueKind.LITERAL` (the union discriminator).
        value: The literal token text.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal[AttributeValueKind.LITERAL] = Field(
        default=AttributeValueKind.LITERAL, description="Discriminator identifying a literal value."
    )
    value: str = Field(..., description="The literal token text.")


class ReferenceValue(BaseModel):
    """An attribute value that references a page.

    Attributes:
        kind: Always :attr:`AttributeValueKind.REFERENCE` (the union discriminator).
        name: The name (title) of the referenced page.
        link: A reference link to the page named by :attr:`name`.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal[AttributeValueKind.REFERENCE] = Field(
        default=AttributeValueKind.REFERENCE, description="Discriminator identifying a reference value."
    )
    name: str = Field(..., description="The name — the title of the referenced page.")
    link: VertexLink = Field(..., description="Reference link to the page named by `name`.")


type AttributeValue = LiteralValue | ReferenceValue
"""A single attribute-assignment value: a :class:`LiteralValue` or a :class:`ReferenceValue`.

A discriminated union keyed on the ``kind`` field; validate a raw mapping with
:data:`attribute_value_adapter`.
"""

attribute_value_adapter: Final[TypeAdapter[AttributeValue]] = TypeAdapter(
    Annotated[AttributeValue, Field(discriminator="kind")]
)
"""Validate a raw mapping into the matching :data:`AttributeValue` subtype.

A Pydantic :class:`~pydantic.TypeAdapter` that discriminates on the ``kind`` field.
"""


class AttributeAssignment(BaseModel):
    """A Roam attribute assignment: an :class:`Attribute` paired with its ordered values.

    Attributes:
        attribute: The attribute (the page named before ``::``).
        values: The ordered values assigned to the attribute (after ``::``).
    """

    model_config = ConfigDict(frozen=True)

    attribute: Attribute = Field(..., description="The attribute — the page named before `::`.")
    values: tuple[Annotated[AttributeValue, Field(discriminator="kind")], ...] = Field(
        ..., description="The ordered values assigned to the attribute."
    )
