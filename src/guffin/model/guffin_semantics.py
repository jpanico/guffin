"""Guffin's own attribute vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Enumerations**: :class:`GuffinSemantics` — the attributes Guffin recognizes, each member a
  :class:`GuffinAttribute` in the :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain;
  :class:`Role` — the role a Guffin attribute plays (publishing / semantics).
- **Models**: :class:`GuffinAttribute` — an :class:`~guffin.model.attribute.Attribute` pinned to the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain and carrying a :class:`Role`.
"""

import enum

from pydantic import Field, field_validator

from guffin.model.attribute import Attribute, AttributeDomain


class Role(enum.StrEnum):
    """The role a Guffin attribute plays.

    Attributes:
        PUBLISHING: A publishing role — the attribute contributes to bibliographic/output metadata.
        SEMANTICS: A semantics role — the attribute conveys structural meaning about the content.
    """

    PUBLISHING = "publishing"
    SEMANTICS = "semantics"


class GuffinAttribute(Attribute):
    """A Guffin-domain :class:`~guffin.model.attribute.Attribute` that also carries a :class:`Role`.

    Specializes :class:`~guffin.model.attribute.Attribute` by pinning :attr:`domain` to
    :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` (any other value is rejected) and adding a
    required :attr:`role`.

    Attributes:
        domain: Always :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`.
        role: The role this attribute plays.
    """

    domain: AttributeDomain = Field(default=AttributeDomain.GUFFIN, description="Always the guffin domain.")
    role: Role = Field(..., description="The role this attribute plays.")

    @field_validator("domain")
    @classmethod
    def _domain_must_be_guffin(cls, value: AttributeDomain) -> AttributeDomain:
        """Reject any domain other than :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN`."""
        if value is not AttributeDomain.GUFFIN:
            raise ValueError(f"GuffinAttribute.domain is fixed to {AttributeDomain.GUFFIN!r}, got {value!r}")
        return value


class GuffinSemantics(enum.Enum):
    """The attributes Guffin recognizes, each a :class:`GuffinAttribute` in the guffin domain.

    Each member's value is the :class:`GuffinAttribute` for that attribute — its name paired with the
    :class:`Role` it plays.  Every attribute defined here is a :attr:`Role.PUBLISHING` attribute.

    Attributes:
        TITLE: The document title.
        AUTHORS: The document author(s).
        DATE: The document date.
        IDENTIFIER: The document identifier.
    """

    _value_: GuffinAttribute

    TITLE = GuffinAttribute(name="title", role=Role.PUBLISHING)
    AUTHORS = GuffinAttribute(name="authors", role=Role.PUBLISHING)
    DATE = GuffinAttribute(name="date", role=Role.PUBLISHING)
    IDENTIFIER = GuffinAttribute(name="identifier", role=Role.PUBLISHING)
