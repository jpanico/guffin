"""Normalized model of a Roam attribute assignment (``<attribute>:: <value>, …``).

A Roam attribute assignment names an attribute — itself a Roam *Page* — and assigns it an ordered
list of values, each of which is either a bare literal token or a reference to another page.  This
module models that construct decoupled from the Roam/parsing layer: page references are captured as
:class:`~guffin.model.vertex_link.VertexLink` pointers rather than raw Roam UIDs or strings.

Public symbols:

- **Type aliases**: :data:`AttributeValue` — discriminated union of :class:`LiteralValue` and
  :class:`ReferenceValue`.
- **Enumerations**: :class:`AttributeDomain` — the namespaces an :class:`Attribute` may belong to
  (default / guffin); :class:`AttributeValueKind` — the two value kinds (literal / reference).
- **Models**: :class:`Attribute` — a Roam attribute's graph-independent identity (name + domain;
  equality and hashing are identity-based, so a subclass instance compares equal to any
  :class:`Attribute` with the same identity);
  :class:`AttributeInstance` — an occurrence of an :class:`Attribute` bound to a specific Roam
  database via a runtime link to its page, the thing preceding ``::``; :class:`LiteralValue`
  — a bare literal value; :class:`ReferenceValue` — a value that references a page; and
  :class:`AttributeAssignment` — an :class:`AttributeInstance` paired with its ordered values.
- **Adapters**: :data:`attribute_value_adapter` — Pydantic :class:`~pydantic.TypeAdapter` for
  validating a raw mapping into the appropriate :data:`AttributeValue`.
- **Functions**: :func:`attribute_value_text` — an :data:`AttributeValue`'s text (literal value or
  reference name); :func:`sole_value` — the single value of an :class:`AttributeAssignment` (raises
  unless it has exactly one); :func:`sole_value_text` — the text of that single value;
  :func:`is_assignment_for` — whether an :class:`AttributeAssignment` assigns a given
  :class:`Attribute` (identity: name + domain); :func:`verify_assignment_for` — its assertion
  form, raising when the assignment is for any other attribute; :func:`find_assignment_for` —
  the first of a collection of assignments that is for a given :class:`Attribute` (warning when
  more than one matches, since multiple-assignment semantics are undefined);
  :func:`verified_sole_value_text` — the text of an assignment's single value, after verifying
  the assignment is for a given :class:`Attribute`.
"""

import enum
import logging
from collections.abc import Sequence
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, validate_call

from guffin.model.vertex_link import VertexLink

logger = logging.getLogger(__name__)


class AttributeDomain(enum.StrEnum):
    """The namespace an :class:`Attribute` belongs to.

    Attributes:
        DEFAULT: The default namespace, for attributes with no reserved domain.
        GUFFIN: Guffin's own reserved namespace.
    """

    DEFAULT = "default"
    GUFFIN = "guffin"


class AttributeValueKind(enum.StrEnum):
    """The kind of an attribute-assignment value, used as the discriminator of :data:`AttributeValue`.

    Attributes:
        LITERAL: A bare literal token (:class:`LiteralValue`).
        REFERENCE: A reference to a page (:class:`ReferenceValue`).
    """

    LITERAL = "literal"
    REFERENCE = "reference"


class Attribute(BaseModel):
    """A Roam attribute — the identity of the page named before the ``::`` separator.

    Runtime-independent: an :class:`Attribute` is described purely by its name and domain, both of
    which are stable across graphs.  It carries no reference to any particular Roam database instance,
    so the same :class:`Attribute` denotes "the attribute called *name* in *domain*" regardless of
    which graph it was read from.  (Contrast :class:`AttributeInstance`, which binds this identity to a
    specific graph's page via a runtime link.)

    Equality and hashing are **identity-based**: two attributes are equal exactly when their
    ``name`` + ``domain`` pairs are equal.  Fields added by subclasses play no part, so a subclass
    instance compares equal to any :class:`Attribute` carrying the same identity.

    Attributes:
        name: The attribute name, i.e. the title of the referenced Roam *Page*.
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
    :attr:`link` binds it to the runtime identity of a specific Roam database instance — it resolves
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


class AttributeAssignment(BaseModel):
    """A Roam attribute assignment: an :class:`AttributeInstance` paired with its ordered values.

    Attributes:
        attribute: The attribute (the page named before ``::``).
        values: The ordered values assigned to the attribute (after ``::``).
    """

    model_config = ConfigDict(frozen=True)

    attribute: AttributeInstance = Field(..., description="The attribute — the page named before `::`.")
    values: tuple[Annotated[AttributeValue, Field(discriminator="kind")], ...] = Field(
        ..., description="The ordered values assigned to the attribute."
    )


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


@validate_call
def sole_value(assignment: AttributeAssignment) -> AttributeValue:
    """Return the single value of *assignment*, requiring it to carry exactly one.

    Args:
        assignment: An attribute assignment expected to have exactly one value.

    Returns:
        The assignment's sole :data:`AttributeValue`.

    Raises:
        ValueError: If *assignment* does not have exactly one value.
    """
    if len(assignment.values) != 1:
        name: Final[str] = assignment.attribute.definition.name
        raise ValueError(f"expected exactly one value for attribute {name!r}, got {len(assignment.values)}")
    return assignment.values[0]


@validate_call
def sole_value_text(assignment: AttributeAssignment) -> str:
    """Return the text of *assignment*'s single value, requiring it to carry exactly one.

    Composes :func:`sole_value` with :func:`attribute_value_text`.

    Args:
        assignment: An attribute assignment expected to have exactly one value.

    Returns:
        The text of the assignment's sole value (the literal token or the referenced page name).

    Raises:
        ValueError: If *assignment* does not have exactly one value.
    """
    return attribute_value_text(sole_value(assignment))


@validate_call
def is_assignment_for(assignment: AttributeAssignment, attribute: Attribute) -> bool:
    """Return whether *assignment* assigns *attribute*.

    Delegates to :class:`Attribute` equality, which is identity-based (name + domain), so the
    assignment matches when its attribute definition carries the same identity — nothing else
    participates in the comparison.

    Args:
        assignment: The attribute assignment to test.
        attribute: The attribute to match against.

    Returns:
        ``True`` when the assignment's attribute equals *attribute*, else ``False``.
    """
    return assignment.attribute.definition == attribute


@validate_call
def verify_assignment_for(assignment: AttributeAssignment, attribute: Attribute) -> None:
    """Require *assignment* to be for *attribute*, raising when it is not.

    The assertion form of :func:`is_assignment_for`: passes silently when the assignment's
    attribute equals *attribute* (identity: name + domain), and raises a descriptive error
    naming both identities otherwise.

    Args:
        assignment: The attribute assignment to verify.
        attribute: The attribute the assignment must be for.

    Raises:
        ValueError: If *assignment* is not for *attribute*.
    """
    if is_assignment_for(assignment, attribute):
        return
    assignment_attribute: Final[Attribute] = assignment.attribute.definition
    raise ValueError(
        f"expected an assignment of {attribute.name!r} in the {attribute.domain} domain, "
        f"got {assignment_attribute.name!r} in {assignment_attribute.domain}"
    )


@validate_call
def find_assignment_for(
    assignments: Sequence[AttributeAssignment] | None, attribute: Attribute
) -> AttributeAssignment | None:
    """Return the first of *assignments* that is for *attribute*, or ``None``.

    An assignment matches per :func:`is_assignment_for` (identity: name + domain).  The semantics
    of multiple assignments of the same attribute within one collection are undefined (neither
    Guffin nor Roam defines them), so when more than one matches, a warning is logged and the
    first wins.

    Args:
        assignments: The attribute assignments to search; ``None`` is treated as empty.
        attribute: The attribute to match.

    Returns:
        The first matching :class:`AttributeAssignment`, or ``None`` when no assignment is for
        *attribute*.
    """
    matches: Final[list[AttributeAssignment]] = [
        assignment for assignment in assignments or () if is_assignment_for(assignment, attribute)
    ]
    if not matches:
        return None
    if len(matches) > 1:
        logger.warning(
            "%d assignments of %r in the %s domain in one collection; "
            "multiple-assignment semantics are undefined — using the first",
            len(matches),
            attribute.name,
            attribute.domain,
        )
    return matches[0]


@validate_call
def verified_sole_value_text(assignment: AttributeAssignment, attribute: Attribute) -> str:
    """Return the text of *assignment*'s single value, first verifying the assignment is for *attribute*.

    Composes :func:`verify_assignment_for` (rejecting an assignment of any other attribute) with
    :func:`sole_value_text` (requiring exactly one value).

    Args:
        assignment: The attribute assignment to verify and read (one value expected).
        attribute: The attribute the assignment must be for (identity: name + domain).

    Returns:
        The text of the assignment's sole value.

    Raises:
        ValueError: If *assignment* is not for *attribute*, or does not carry exactly one value.
    """
    verify_assignment_for(assignment, attribute)
    return sole_value_text(assignment)
