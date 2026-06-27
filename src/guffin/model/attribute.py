"""Normalized model of a Roam attribute assignment (``<attribute>:: <value>, …``).

A Roam attribute assignment names an attribute — itself a Roam *Page* — and assigns it an ordered
list of values, each of which is either a bare literal token or a reference to another page.  This
module models that construct decoupled from the Roam/parsing layer: page references are captured as
:class:`~guffin.model.link.VertexLink` pointers rather than raw Roam UIDs or strings.

Public symbols:

- **Type aliases**: :data:`AttributeValue` — discriminated union of :class:`LiteralValue` and
  :class:`ReferenceValue`.
- **Enumerations**: :class:`AttributeValueKind` — the two value kinds (literal / reference).
- **Models**: :class:`Attribute` — the named attribute (a page) preceding ``::``; :class:`LiteralValue`
  — a bare literal value; :class:`ReferenceValue` — a value that references a page; and
  :class:`AttributeAssignment` — an :class:`Attribute` paired with its ordered values.
- **Adapters**: :data:`attribute_value_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for
  validating a raw mapping into the appropriate :data:`AttributeValue`.
"""

import enum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from guffin.model.link import VertexLink


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
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="The attribute name — the title of the referenced page.")
    link: VertexLink = Field(..., description="Reference link to the page named by `name`.")


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
