"""Guffin's own attribute vocabulary — the attributes Guffin recognizes in its reserved domain.

Public symbols:

- **Enumerations**: :class:`GuffinAttribute` — the attributes Guffin recognizes in the
  :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` domain.
"""

import enum

from guffin.model.attribute import AttributeDomain


class GuffinAttribute(enum.StrEnum):
    """The attributes Guffin recognizes, all in the :attr:`DOMAIN` namespace.

    Each member's value is the attribute name as it appears in Roam (the page named before ``::``).
    :attr:`DOMAIN` — bound to :attr:`~guffin.model.attribute.AttributeDomain.GUFFIN` — is the shared
    :attr:`~guffin.model.attribute.Attribute.domain` every member belongs to; it is a class-level
    constant, not itself an attribute name (and so does not appear when iterating the enum).

    Attributes:
        DOMAIN: The shared :attr:`~guffin.model.attribute.Attribute.domain` of every member.
        TITLE: The document title.
        AUTHORS: The document author(s).
        DATE: The document date.
        IDENTIFIER: The document identifier.
    """

    DOMAIN = enum.nonmember(AttributeDomain.GUFFIN)

    TITLE = "title"
    AUTHORS = "authors"
    DATE = "date"
    IDENTIFIER = "identifier"
