"""Tests for guffin.model.guffin_semantics."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import AttributeDomain
from guffin.model.guffin_semantics import GuffinAttribute, Level, Role


class TestGuffinAttribute:
    """GuffinAttribute pins its domain to GUFFIN and requires a role and a level."""

    def test_domain_defaults_to_guffin(self) -> None:
        """The domain is the guffin domain without being passed."""
        attribute = GuffinAttribute(name="title", role=Role.PUBLISHING, level=Level.DOCUMENT)
        assert attribute.domain is AttributeDomain.GUFFIN

    def test_non_guffin_domain_is_rejected(self) -> None:
        """Constructing with any domain other than GUFFIN raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", role=Role.SEMANTICS, level=Level.DOCUMENT, domain=AttributeDomain.DEFAULT)

    def test_role_is_required(self) -> None:
        """Constructing without a role raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", level=Level.DOCUMENT)  # type: ignore[call-arg]

    def test_level_is_required(self) -> None:
        """Constructing without a level raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", role=Role.PUBLISHING)  # type: ignore[call-arg]
