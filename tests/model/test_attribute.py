"""Tests for guffin.model.attribute."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeAssignment,
    AttributeValueKind,
    LiteralValue,
    ReferenceValue,
    attribute_value_adapter,
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
            attribute=Attribute(name="attribute1", link=_LINK),
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
            attribute=Attribute(name="a", link=_LINK),
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
        attribute = Attribute(name="a", link=_LINK)
        with pytest.raises(ValidationError):
            attribute.name = "b"  # type: ignore[misc]

    def test_literal_value_is_frozen(self) -> None:
        """Reassigning a LiteralValue field raises."""
        value = LiteralValue(value="x")
        with pytest.raises(ValidationError):
            value.value = "y"  # type: ignore[misc]

    def test_attribute_assignment_is_frozen(self) -> None:
        """Reassigning an AttributeAssignment field raises."""
        assignment = AttributeAssignment(attribute=Attribute(name="a", link=_LINK), values=(LiteralValue(value="x"),))
        with pytest.raises(ValidationError):
            assignment.attribute = Attribute(name="b", link=_LINK)  # type: ignore[misc]
