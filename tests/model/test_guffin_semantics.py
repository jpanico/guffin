"""Tests for guffin.model.guffin_semantics."""

import pytest
from pydantic import ValidationError

from guffin.model.attribute import AttributeDomain
from guffin.model.guffin_semantics import GuffinAttribute, Role
from guffin.model.link import VertexLink, VertexLinkKind

_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")


class TestGuffinAttribute:
    """GuffinAttribute pins its domain to GUFFIN and requires a role."""

    def test_domain_defaults_to_guffin(self) -> None:
        """The domain is the guffin domain without being passed."""
        attribute = GuffinAttribute(name="title", link=_LINK, role=Role.PUBLISHING)
        assert attribute.domain is AttributeDomain.GUFFIN

    def test_non_guffin_domain_is_rejected(self) -> None:
        """Constructing with any domain other than GUFFIN raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", link=_LINK, role=Role.SEMANTICS, domain=AttributeDomain.DEFAULT)

    def test_role_is_required(self) -> None:
        """Constructing without a role raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", link=_LINK)  # type: ignore[call-arg]
