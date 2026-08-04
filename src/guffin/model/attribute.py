"""Normalized model of an attribute assignment (``<attribute>:: <value>, …``).

An attribute assignment names an attribute — itself a page in the source graph — and assigns it an
ordered list of values, each of which is either a bare literal token or a reference to another
page.  This module models that construct decoupled from any source's own encoding: page references
are captured as :class:`~guffin.model.vertex_link.VertexLink` pointers rather than raw source UIDs
or strings.

Public symbols:

- **Type aliases**: :data:`AttributeValue` — discriminated union of :class:`LiteralValue` and
  :class:`ReferenceValue`.
- **Enumerations**: :class:`AttributeDomain` — the namespaces an :class:`Attribute` may belong to
  (default / guffin); :class:`AttributeValueKind` — the two value kinds (literal / reference).
- **Models**: :class:`Attribute` — an attribute's graph-independent identity (name + domain;
  equality and hashing are identity-based, so a subclass instance compares equal to any
  :class:`Attribute` with the same identity);
  :class:`AttributeInstance` — an occurrence of an :class:`Attribute` bound to a specific source
  graph via a runtime link to its page, the thing preceding ``::``; :class:`LiteralValue`
  — a bare literal value; :class:`ReferenceValue` — a value that references a page.
- **Adapters**: :data:`attribute_value_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for
  validating a raw mapping into the appropriate :data:`AttributeValue`.
- **Functions**: :func:`attribute_value_text` — an :data:`AttributeValue`'s text (literal value or
  reference name).
"""

import enum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, validate_call

from guffin.model.vertex_link import VertexLink


class AttributeDomain(enum.StrEnum):
    """The namespace an :class:`Attribute` belongs to.

    Attributes:
        DEFAULT: The default namespace, for attributes with no reserved domain.
        GUFFIN: Guffin's own reserved namespace.
    """

    DEFAULT = "default"
    GUFFIN = "guffin"

    @property
    def is_guffin(self) -> bool:
        """Whether this domain belongs to the Guffin system rather than to the end-user.

        Every attribute is metadata by nature; what sets the Guffin system's domain apart is
        ownership: its attributes carry semantics for the Guffin system alone (bibliographic
        fields, structural tags, render directives) and never appear directly within the output
        content, whereas an end-user domain's assignments are part of the authored document
        itself.
        """
        return self is AttributeDomain.GUFFIN


class AttributeValueKind(enum.StrEnum):
    """The kind of an attribute-assignment value, used as the discriminator of :data:`AttributeValue`.

    Attributes:
        LITERAL: A bare literal token (:class:`LiteralValue`).
        REFERENCE: A reference to a page (:class:`ReferenceValue`).
    """

    LITERAL = "literal"
    REFERENCE = "reference"


class Attribute(BaseModel):
    """An attribute — the identity of the page named before the ``::`` separator.

    Runtime-independent: an :class:`Attribute` is described purely by its name and domain, both of
    which are stable across graphs.  It carries no reference to any particular source graph, so the
    same :class:`Attribute` denotes "the attribute called *name* in *domain*" regardless of which
    graph it was read from.  (Contrast :class:`AttributeInstance`, which binds this identity to a
    specific graph's page via a runtime link.)

    Equality and hashing are **identity-based**: two attributes are equal exactly when their
    ``name`` + ``domain`` pairs are equal.  Fields added by subclasses play no part, so a subclass
    instance compares equal to any :class:`Attribute` carrying the same identity.

    Attributes:
        name: The attribute name, i.e. the title of the referenced page.
        domain: The namespace the attribute belongs to; defaults to :attr:`AttributeDomain.DEFAULT`.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="The attribute name — the title of the referenced page.")
    domain: AttributeDomain = Field(
        default=AttributeDomain.DEFAULT, description="The namespace the attribute belongs to."
    )

    def __eq__(self, other: object) -> bool:
        """Return whether *other* is an :class:`Attribute` with the same identity (name + domain)."""
        if not isinstance(other, Attribute):
            return NotImplemented
        return self.name == other.name and self.domain == other.domain

    def __hash__(self) -> int:
        """Hash the identity (name + domain) pair, consistently with :meth:`__eq__`."""
        return hash((self.name, self.domain))


class AttributeInstance(BaseModel):
    """A particular occurrence of an attribute — its :class:`Attribute` paired with a link to its page.

    Runtime-dependent: whereas the :class:`Attribute` :attr:`definition` is graph-independent, the
    :attr:`link` binds it to the runtime identity of a specific source graph — it resolves
    to the attribute page (by UID) within the graph this instance was read from, and is meaningful
    only against that graph.

    Attributes:
        definition: The attribute (name + domain) this is an instance of.
        link: A reference link to the page named by the attribute.
    """

    model_config = ConfigDict(frozen=True)

    definition: Attribute = Field(..., description="The attribute (name + domain) this is an instance of.")
    link: VertexLink = Field(..., description="Reference link to the attribute's page.")


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


@validate_call
def attribute_value_text(value: AttributeValue) -> str:
    """Return *value*'s text — its literal token or, for a reference, the referenced page name.

    Args:
        value: The attribute-assignment value to read.

    Returns:
        :attr:`LiteralValue.value` for a :class:`LiteralValue`, or :attr:`ReferenceValue.name` for a
        :class:`ReferenceValue`.
    """
    return value.name if isinstance(value, ReferenceValue) else value.value
