"""Anchoring: where an attribute may attach to a :class:`~guffin.model.vertex_tree.VertexTree`.

The anchoring affordances the model supplies — the constraint axes a host vertex can be required
to satisfy — independent of any particular attribute vocabulary's use of them.  An anchor
constrains two orthogonal things: the host's :class:`~guffin.model.vertex.VertexType`, and its
position in the tree.

Public symbols:

- **Enumerations**: :class:`TreePosition` — the positional axis (anywhere / root);
  :class:`AttributeAnchor` — the anchor kinds, each member carrying its
  :class:`~guffin.model.vertex.VertexType` set and its :class:`TreePosition`.

Sits just above the structural primitives in the ``model/`` conceptual stack: it depends only on
:mod:`~guffin.model.vertex`, and any vocabulary declared over the model may depend on it.
"""

import enum
from typing import Self

from guffin.model.vertex import VertexType


class TreePosition(enum.StrEnum):
    """Where in a :class:`~guffin.model.vertex_tree.VertexTree` an attribute's host vertex may sit.

    The positional axis of an :class:`AttributeAnchor`, independent of the host's
    :class:`~guffin.model.vertex.VertexType`.

    Attributes:
        ANYWHERE: No positional constraint — any vertex in the tree.
        ROOT: Only the tree's root vertex (the export target itself).
    """

    ANYWHERE = "anywhere"
    ROOT = "root"


class AttributeAnchor(enum.StrEnum):
    """Where an attribute attaches: the kind of vertex, and its position in the tree.

    Each member carries two constraint axes, and a host vertex must satisfy both:

    - :attr:`vertex_types` — the set of :class:`~guffin.model.vertex.VertexType` the attribute
      may be declared on.  The :attr:`BLOCK`, :attr:`ANY`, and :attr:`ROOT` sets are derived
      from :class:`~guffin.model.vertex.VertexType` itself, so a future vertex type is covered
      without touching this enum.
    - :attr:`tree_position` — where in the tree the host may sit, independent of its type.

    Attributes:
        vertex_types: The :class:`~guffin.model.vertex.VertexType` set this anchor corresponds to.
        tree_position: The :class:`TreePosition` this anchor requires of its host.
        PAGE: The attribute attaches to a page vertex (the whole document).
        HEADING: The attribute attaches to a heading vertex (a section).
        PDF: The attribute attaches to a PDF vertex (an embedded PDF asset).
        CODE_BLOCK: The attribute attaches to a code-block vertex (a fenced code listing).
        BLOCK: The attribute attaches to any block vertex — every vertex type except a page.
        ANY: The attribute attaches to any vertex, of every type, anywhere.
        ROOT: The attribute attaches to the tree's root vertex, whatever its type — a page for a
            page export, a heading or text block for a subtree export.
    """

    def __new__(cls, value: str, vertex_types: frozenset[VertexType], tree_position: TreePosition) -> Self:
        """Create a member whose string value is *value*, carrying *vertex_types* and *tree_position*."""
        member = str.__new__(cls, value)
        member._value_ = value
        member.vertex_types = vertex_types
        member.tree_position = tree_position
        return member

    vertex_types: frozenset[VertexType]
    tree_position: TreePosition

    PAGE = ("page", frozenset({VertexType.PAGE}), TreePosition.ANYWHERE)
    HEADING = ("heading", frozenset({VertexType.HEADING}), TreePosition.ANYWHERE)
    PDF = ("pdf", frozenset({VertexType.PDF}), TreePosition.ANYWHERE)
    CODE_BLOCK = ("code-block", frozenset({VertexType.CODE_BLOCK}), TreePosition.ANYWHERE)
    BLOCK = ("block", frozenset(VertexType) - {VertexType.PAGE}, TreePosition.ANYWHERE)
    ANY = ("any", frozenset(VertexType), TreePosition.ANYWHERE)
    ROOT = ("root", frozenset(VertexType), TreePosition.ROOT)
