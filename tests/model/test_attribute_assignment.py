"""Tests for guffin.model.attribute_assignment."""

import logging

import pytest
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
    ReferenceValue,
)
from guffin.model.attribute_assignment import (
    AttributeAssignment,
    find_assignment_for,
    is_assignment_for,
    sole_value,
    sole_value_text,
    verified_sole_value_text,
    verify_assignment_for,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind

_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")


# ---------------------------------------------------------------------------
# TestAttributeAssignment
# ---------------------------------------------------------------------------


class TestAttributeAssignment:
    """Tests for AttributeAssignment construction, value discrimination, and round-tripping."""

    @staticmethod
    def _make() -> AttributeAssignment:
        return AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="attribute1"), link=_LINK),
            values=(LiteralValue(value="5"), ReferenceValue(name="callouts demo", link=_LINK)),
        )

    def test_values_round_trip_discriminates(self) -> None:
        """Dumping and revalidating an assignment restores each value's concrete subtype."""
        original = self._make()
        restored = AttributeAssignment.model_validate(original.model_dump())
        assert restored == original
        assert isinstance(restored.values[0], LiteralValue)
        assert isinstance(restored.values[1], ReferenceValue)

    def test_list_values_coerced_to_tuple(self) -> None:
        """A list of values is coerced to an immutable tuple."""
        assignment = AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="a"), link=_LINK),
            values=[LiteralValue(value="x")],  # type: ignore[arg-type]
        )
        assert isinstance(assignment.values, tuple)

    def test_is_frozen(self) -> None:
        """Reassigning an AttributeAssignment field raises."""
        assignment = AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="a"), link=_LINK), values=(LiteralValue(value="x"),)
        )
        with pytest.raises(ValidationError):
            assignment.attribute = AttributeInstance(definition=Attribute(name="b"), link=_LINK)  # type: ignore[misc]


def _assignment(*values: LiteralValue | ReferenceValue) -> AttributeAssignment:
    """Build an AttributeAssignment with the given values."""
    return AttributeAssignment(attribute=AttributeInstance(definition=Attribute(name="a"), link=_LINK), values=values)


class TestSoleValue:
    """sole_value() returns the one value, requiring exactly one."""

    def test_returns_the_single_value(self) -> None:
        """A one-value assignment yields that value."""
        only = LiteralValue(value="x")
        assert sole_value(_assignment(only)) == only

    def test_zero_values_raises(self) -> None:
        """An assignment with no values raises ValueError."""
        with pytest.raises(ValueError):
            sole_value(_assignment())

    def test_multiple_values_raises(self) -> None:
        """An assignment with more than one value raises ValueError."""
        with pytest.raises(ValueError):
            sole_value(_assignment(LiteralValue(value="a"), LiteralValue(value="b")))


class TestSoleValueText:
    """sole_value_text() returns the text of the one value."""

    def test_returns_literal_text(self) -> None:
        """The sole literal value's text is returned."""
        assert sole_value_text(_assignment(LiteralValue(value="2027-01-01"))) == "2027-01-01"

    def test_returns_reference_text(self) -> None:
        """The sole reference value's name is returned."""
        assert sole_value_text(_assignment(ReferenceValue(name="SomePage", link=_LINK))) == "SomePage"

    def test_multiple_values_raises(self) -> None:
        """It propagates sole_value()'s error when there isn't exactly one value."""
        with pytest.raises(ValueError):
            sole_value_text(_assignment(LiteralValue(value="a"), LiteralValue(value="b")))


class TestIsAssignmentFor:
    """is_assignment_for() matches an assignment against an Attribute's name + domain identity."""

    def test_same_name_and_domain_matches(self) -> None:
        """An assignment matches the attribute it was built for."""
        assert is_assignment_for(_assignment(), Attribute(name="a")) is True

    def test_different_name_does_not_match(self) -> None:
        """An attribute with another name does not match."""
        assert is_assignment_for(_assignment(), Attribute(name="b")) is False

    def test_different_domain_does_not_match(self) -> None:
        """The same name in another domain does not match — identity is the name + domain pair."""
        assert is_assignment_for(_assignment(), Attribute(name="a", domain=AttributeDomain.GUFFIN)) is False

    def test_guffin_domain_assignment_matches_its_attribute(self) -> None:
        """A guffin-domain assignment matches an Attribute carrying the same name and domain."""
        guffin_assignment = AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="a", domain=AttributeDomain.GUFFIN), link=_LINK),
            values=(),
        )
        assert is_assignment_for(guffin_assignment, Attribute(name="a", domain=AttributeDomain.GUFFIN)) is True


class TestVerifyAssignmentFor:
    """verify_assignment_for() passes silently on a match and raises descriptively otherwise."""

    def test_matching_attribute_passes(self) -> None:
        """An assignment for the expected attribute verifies without raising."""
        verify_assignment_for(_assignment(), Attribute(name="a"))

    def test_wrong_attribute_raises_with_both_identities(self) -> None:
        """The error names the expected and the actual identity."""
        with pytest.raises(ValueError, match="expected an assignment of 'b'.*got 'a'"):
            verify_assignment_for(_assignment(), Attribute(name="b"))

    def test_wrong_domain_raises(self) -> None:
        """The same name in a different domain is rejected — verification is by identity."""
        with pytest.raises(ValueError, match="expected an assignment"):
            verify_assignment_for(_assignment(), Attribute(name="a", domain=AttributeDomain.GUFFIN))


def _assignment_of(name: str, domain: AttributeDomain = AttributeDomain.DEFAULT) -> AttributeAssignment:
    """Build a value-less AttributeAssignment for the attribute named *name* in *domain*."""
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=name, domain=domain), link=_LINK), values=()
    )


class TestFindAssignmentFor:
    """find_assignment_for() returns the first assignment for an attribute, or None."""

    def test_finds_matching_assignment(self) -> None:
        """The assignment for the sought attribute is returned from a mixed collection."""
        sought = _assignment_of("b")
        assert find_assignment_for([_assignment_of("a"), sought], Attribute(name="b")) == sought

    def test_returns_first_match_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """With several assignments for the attribute, the first wins and a warning is logged.

        Neither Guffin nor Roam defines the semantics of assigning the same attribute more than
        once on one node, so the duplicate is surfaced rather than silently ignored.
        """
        first = _assignment_of("a")
        with caplog.at_level(logging.WARNING, logger="guffin.model.attribute_assignment"):
            result = find_assignment_for([first, _assignment_of("a")], Attribute(name="a"))
        assert result is not None
        assert result == first
        assert any("multiple-assignment semantics are undefined" in r.message for r in caplog.records)

    def test_single_match_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """A single matching assignment (amid other attributes) produces no warning."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.attribute_assignment"):
            find_assignment_for([_assignment_of("a"), _assignment_of("b")], Attribute(name="a"))
        assert not caplog.records

    def test_none_when_no_match(self) -> None:
        """A collection with no assignment for the attribute yields None."""
        assert find_assignment_for([_assignment_of("a")], Attribute(name="b")) is None

    def test_none_collection_treated_as_empty(self) -> None:
        """A None collection (a vertex without assignments) yields None."""
        assert find_assignment_for(None, Attribute(name="a")) is None

    def test_matches_by_identity_not_domain_alone(self) -> None:
        """The same name in a different domain does not match."""
        assert find_assignment_for([_assignment_of("a")], Attribute(name="a", domain=AttributeDomain.GUFFIN)) is None


class TestVerifiedSoleValueText:
    """verified_sole_value_text() reads the one value's text after verifying the assignment's attribute."""

    def test_returns_sole_value_text_for_matching_attribute(self) -> None:
        """A one-value assignment for the expected attribute yields the value's text."""
        assert verified_sole_value_text(_assignment(LiteralValue(value="chapter")), Attribute(name="a")) == "chapter"

    def test_wrong_attribute_raises(self) -> None:
        """An assignment of a different attribute is rejected."""
        with pytest.raises(ValueError, match="expected an assignment of 'b'"):
            verified_sole_value_text(_assignment(LiteralValue(value="x")), Attribute(name="b"))

    def test_wrong_domain_raises(self) -> None:
        """The same name in a different domain is rejected — verification is by identity."""
        with pytest.raises(ValueError, match="expected an assignment"):
            verified_sole_value_text(
                _assignment(LiteralValue(value="x")), Attribute(name="a", domain=AttributeDomain.GUFFIN)
            )

    def test_multiple_values_raises(self) -> None:
        """It propagates sole_value()'s error when there isn't exactly one value."""
        with pytest.raises(ValueError):
            verified_sole_value_text(_assignment(LiteralValue(value="a"), LiteralValue(value="b")), Attribute(name="a"))
