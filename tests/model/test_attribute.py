"""Tests for guffin.model.attribute."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    AttributeValueKind,
    LiteralValue,
    ReferenceValue,
    attribute_value_adapter,
    attribute_value_text,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind

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


class TestAttributeValueText:
    """attribute_value_text() yields a literal's value or a reference's name."""

    def test_literal_value_returns_its_value(self) -> None:
        """A LiteralValue's text is its literal token."""
        assert attribute_value_text(LiteralValue(value="5")) == "5"

    def test_reference_value_returns_its_name(self) -> None:
        """A ReferenceValue's text is the referenced page name."""
        assert attribute_value_text(ReferenceValue(name="callouts demo", link=_LINK)) == "callouts demo"


class _ExtendedAttribute(Attribute):
    """An Attribute subclass with an extra field, for identity-equality tests."""

    extra: str = "x"


class TestAttributeEquality:
    """Attribute equality and hashing are identity-based: the name + domain pair, nothing else."""

    def test_same_identity_is_equal(self) -> None:
        """Two attributes with the same name and domain are equal."""
        assert Attribute(name="a") == Attribute(name="a")

    def test_different_name_is_not_equal(self) -> None:
        """Attributes with different names are unequal."""
        assert Attribute(name="a") != Attribute(name="b")

    def test_different_domain_is_not_equal(self) -> None:
        """The same name in different domains is unequal — identity is the pair."""
        assert Attribute(name="a") != Attribute(name="a", domain=AttributeDomain.GUFFIN)

    def test_subclass_equals_base_with_same_identity(self) -> None:
        """A subclass instance equals a plain Attribute carrying the same identity, both ways."""
        extended = _ExtendedAttribute(name="a", extra="y")
        plain = Attribute(name="a")
        assert extended == plain
        assert plain == extended

    def test_subclass_fields_play_no_part(self) -> None:
        """Subclass instances differing only in subclass fields are equal."""
        assert _ExtendedAttribute(name="a", extra="y") == _ExtendedAttribute(name="a", extra="z")

    def test_hash_is_consistent_with_equality(self) -> None:
        """Equal attributes hash equally, across the subclass boundary."""
        assert hash(_ExtendedAttribute(name="a")) == hash(Attribute(name="a"))

    def test_set_collapses_by_identity(self) -> None:
        """A set keyed by attributes collapses same-identity instances to one element."""
        assert len({Attribute(name="a"), _ExtendedAttribute(name="a"), _ExtendedAttribute(name="a", extra="y")}) == 1

    def test_non_attribute_is_not_equal(self) -> None:
        """Comparison against a non-Attribute object is False, not an error."""
        assert Attribute(name="a") != "a"


class TestAttributeDomainIsGuffin:
    """is_guffin marks the domain owned by the Guffin system, as opposed to the end-user."""

    def test_guffin_domain_is_guffin(self) -> None:
        """The guffin domain belongs to the Guffin system."""
        assert AttributeDomain.GUFFIN.is_guffin

    def test_default_domain_is_end_user(self) -> None:
        """The default domain belongs to the end-user's authored content."""
        assert not AttributeDomain.DEFAULT.is_guffin
