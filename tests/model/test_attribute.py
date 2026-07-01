"""Tests for guffin.model.attribute."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeAssignment,
    AttributeInstance,
    AttributeValueKind,
    LiteralValue,
    ReferenceValue,
    attribute_value_adapter,
    attribute_value_text,
    sole_value,
    sole_value_text,
)
from guffin.model.link import VertexLink, VertexLinkKind

_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")


# ---------------------------------------------------------------------------
# TestAttributeValueDiscrimination
# ---------------------------------------------------------------------------


class TestAttributeValueDiscrimination:
    """Tests that a raw mapping resolves to the correct AttributeValue subtype via the `kind` field."""

    def test_literal_dict_resolves_to_literal_value(self) -> None:
        """A mapping with kind 'literal' validates into a LiteralValue."""
        value = attribute_value_adapter.validate_python({"kind": "literal", "value": "5"})
        assert isinstance(value, LiteralValue)
        assert value.value == "5"

    def test_reference_dict_resolves_to_reference_value(self) -> None:
        """A mapping with kind 'reference' validates into a ReferenceValue (link coerced from a list)."""
        value = attribute_value_adapter.validate_python(
            {"kind": "reference", "name": "callouts demo", "link": ["vertex", "abc123xyz"]}
        )
        assert isinstance(value, ReferenceValue)
        assert value.name == "callouts demo"
        assert value.link == _LINK

    def test_unknown_kind_raises(self) -> None:
        """An unrecognised discriminator value is rejected."""
        with pytest.raises(ValidationError):
            attribute_value_adapter.validate_python({"kind": "bogus", "value": "x"})

    def test_missing_kind_raises(self) -> None:
        """A mapping with no discriminator is rejected."""
        with pytest.raises(ValidationError):
            attribute_value_adapter.validate_python({"value": "x"})


# ---------------------------------------------------------------------------
# TestAttributeValueDefaults
# ---------------------------------------------------------------------------


class TestAttributeValueDefaults:
    """Tests that each value subtype auto-sets its discriminator kind."""

    def test_literal_value_defaults_kind(self) -> None:
        """A constructed LiteralValue carries the LITERAL discriminator without it being passed."""
        assert LiteralValue(value="5").kind is AttributeValueKind.LITERAL

    def test_reference_value_defaults_kind(self) -> None:
        """A constructed ReferenceValue carries the REFERENCE discriminator without it being passed."""
        assert ReferenceValue(name="x", link=_LINK).kind is AttributeValueKind.REFERENCE

    def test_literal_value_requires_value(self) -> None:
        """A LiteralValue without its `value` field is rejected."""
        with pytest.raises(ValidationError):
            LiteralValue()  # type: ignore[call-arg]

    def test_reference_value_requires_name_and_link(self) -> None:
        """A ReferenceValue without its `link` field is rejected."""
        with pytest.raises(ValidationError):
            ReferenceValue(name="x")  # type: ignore[call-arg]


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


# ---------------------------------------------------------------------------
# TestFrozen
# ---------------------------------------------------------------------------


class TestFrozen:
    """Tests that the attribute models are immutable (frozen)."""

    def test_attribute_is_frozen(self) -> None:
        """Reassigning an Attribute field raises."""
        attribute = Attribute(name="a")
        with pytest.raises(ValidationError):
            attribute.name = "b"  # type: ignore[misc]

    def test_attribute_instance_is_frozen(self) -> None:
        """Reassigning an AttributeInstance field raises."""
        instance = AttributeInstance(definition=Attribute(name="a"), link=_LINK)
        with pytest.raises(ValidationError):
            instance.link = _LINK  # type: ignore[misc]

    def test_literal_value_is_frozen(self) -> None:
        """Reassigning a LiteralValue field raises."""
        value = LiteralValue(value="x")
        with pytest.raises(ValidationError):
            value.value = "y"  # type: ignore[misc]

    def test_attribute_assignment_is_frozen(self) -> None:
        """Reassigning an AttributeAssignment field raises."""
        assignment = AttributeAssignment(
            attribute=AttributeInstance(definition=Attribute(name="a"), link=_LINK), values=(LiteralValue(value="x"),)
        )
        with pytest.raises(ValidationError):
            assignment.attribute = AttributeInstance(definition=Attribute(name="b"), link=_LINK)  # type: ignore[misc]


def _assignment(*values: LiteralValue | ReferenceValue) -> AttributeAssignment:
    """Build an AttributeAssignment with the given values."""
    return AttributeAssignment(attribute=AttributeInstance(definition=Attribute(name="a"), link=_LINK), values=values)


class TestAttributeValueText:
    """attribute_value_text() yields a literal's value or a reference's name."""

    def test_literal_value_returns_its_value(self) -> None:
        """A LiteralValue's text is its literal token."""
        assert attribute_value_text(LiteralValue(value="5")) == "5"

    def test_reference_value_returns_its_name(self) -> None:
        """A ReferenceValue's text is the referenced page name."""
        assert attribute_value_text(ReferenceValue(name="callouts demo", link=_LINK)) == "callouts demo"


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
