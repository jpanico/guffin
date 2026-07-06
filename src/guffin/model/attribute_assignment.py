"""A Roam attribute assignment (``<attribute>:: <value>, …``) and the helpers that read it.

An assignment pairs an :class:`~guffin.model.attribute.AttributeInstance` (the attribute named before
``::``) with the ordered list of values assigned to it (after ``::``).  This module models that pairing
and the operations over it, built atop the attribute/value vocabulary in
:mod:`guffin.model.attribute`.

Public symbols:

- **Models**: :class:`AttributeAssignment` — an :class:`~guffin.model.attribute.AttributeInstance`
  paired with its ordered values.
- **Functions**: :func:`sole_value` — the single value of an :class:`AttributeAssignment` (raises
  unless it has exactly one); :func:`sole_value_text` — the text of that single value;
  :func:`is_assignment_for` — whether an :class:`AttributeAssignment` assigns a given
  :class:`~guffin.model.attribute.Attribute` (identity: name + domain); :func:`verify_assignment_for`
  — its assertion form, raising when the assignment is for any other attribute;
  :func:`find_assignment_for` — the first of a collection of assignments that is for a given
  :class:`~guffin.model.attribute.Attribute` (warning when more than one matches, since
  multiple-assignment semantics are undefined); :func:`verified_sole_value_text` — the text of an
  assignment's single value, after verifying the assignment is for a given
  :class:`~guffin.model.attribute.Attribute`.
"""

import logging
from collections.abc import Sequence
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, validate_call

from guffin.model.attribute import (
    Attribute,
    AttributeInstance,
    AttributeValue,
    attribute_value_text,
)

logger = logging.getLogger(__name__)


class AttributeAssignment(BaseModel):
    """A Roam attribute assignment: an :class:`~guffin.model.attribute.AttributeInstance` and its ordered values.

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
def sole_value(assignment: AttributeAssignment) -> AttributeValue:
    """Return the single value of *assignment*, requiring it to carry exactly one.

    Args:
        assignment: An attribute assignment expected to have exactly one value.

    Returns:
        The assignment's sole :data:`~guffin.model.attribute.AttributeValue`.

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

    Composes :func:`sole_value` with :func:`~guffin.model.attribute.attribute_value_text`.

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

    Delegates to :class:`~guffin.model.attribute.Attribute` equality, which is identity-based (name +
    domain), so the assignment matches when its attribute definition carries the same identity —
    nothing else participates in the comparison.

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
