"""Tests for guffin.model.guffin_semantics."""

import pytest
import yaml
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeAssignment,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
)
from guffin.model.guffin_semantics import (
    Anchor,
    GuffinAttribute,
    GuffinSemantics,
    Matter,
    StructuralElement,
    element_type_of,
    matter_of,
)
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import find_guffin_attribute, vertex_adapter
from guffin.model.vertex_tree import VertexTree, VertexTreeDFSIterator

from conftest import FIXTURES_YAML_DIR

_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")


def _assignment(name: str, value: str, domain: AttributeDomain = AttributeDomain.GUFFIN) -> AttributeAssignment:
    """Build a single-value AttributeAssignment for attribute *name* in *domain* carrying *value*."""
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=name, domain=domain), link=_LINK),
        values=(LiteralValue(value=value),),
    )


class TestGuffinAttribute:
    """GuffinAttribute pins its domain to GUFFIN and requires an anchor."""

    def test_domain_defaults_to_guffin(self) -> None:
        """The domain is the guffin domain without being passed."""
        attribute = GuffinAttribute(name="title", anchor=Anchor.PAGE)
        assert attribute.domain is AttributeDomain.GUFFIN

    def test_non_guffin_domain_is_rejected(self) -> None:
        """Constructing with any domain other than GUFFIN raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x", anchor=Anchor.PAGE, domain=AttributeDomain.DEFAULT)

    def test_anchor_is_required(self) -> None:
        """Constructing without an anchor raises."""
        with pytest.raises(ValidationError):
            GuffinAttribute(name="x")  # type: ignore[call-arg]


class TestElementTypeOf:
    """element_type_of validates the attribute identity and coerces the value to a StructuralElement."""

    def test_returns_named_structural_element(self) -> None:
        """A valid element-type assignment yields the named StructuralElement."""
        assert element_type_of(_assignment("element-type", "chapter")) is StructuralElement.CHAPTER

    def test_wrong_attribute_name_rejected(self) -> None:
        """An assignment for a different attribute raises, even if its value is a valid element."""
        with pytest.raises(ValueError):
            element_type_of(_assignment("title", "chapter"))

    def test_wrong_domain_rejected(self) -> None:
        """An element-type assignment outside the guffin domain raises."""
        with pytest.raises(ValueError):
            element_type_of(_assignment("element-type", "chapter", domain=AttributeDomain.DEFAULT))

    def test_unknown_value_rejected(self) -> None:
        """A value that is not a recognised StructuralElement raises."""
        with pytest.raises(ValueError):
            element_type_of(_assignment("element-type", "not-an-element"))


class TestMatterOf:
    """matter_of validates the attribute identity and coerces the value to a Matter."""

    def test_returns_named_matter(self) -> None:
        """A valid matter assignment yields the named Matter."""
        assert matter_of(_assignment("matter", "front-matter")) is Matter.FRONT

    def test_wrong_attribute_name_rejected(self) -> None:
        """An assignment for a different attribute raises, even with a valid matter value."""
        with pytest.raises(ValueError):
            matter_of(_assignment("element-type", "front-matter"))

    def test_unknown_value_rejected(self) -> None:
        """A value that is not a recognised Matter raises."""
        with pytest.raises(ValueError):
            matter_of(_assignment("matter", "middle-matter"))


def _article6_vertex_tree() -> VertexTree:
    """Load the [[Test Article]] 6 VertexTree from its YAML fixture."""
    raw = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_6_vertices.yaml").read_text())
    return VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])


class TestElementTypeOfArticle6Fixture:
    """element_type_of resolves the real element-type tags in the [[Test Article]] 6 fixture."""

    def test_resolves_all_tagged_headings(self) -> None:
        """Every element-type-tagged heading resolves to the StructuralElement its tag names."""
        tree = _article6_vertex_tree()
        resolved = {
            vertex.uid: element_type_of(assignment)
            for vertex in VertexTreeDFSIterator(tree)
            if (assignment := find_guffin_attribute(vertex, GuffinSemantics.ELEMENT_TYPE)) is not None
        }
        assert resolved == {
            "dpoX6c0Pl": StructuralElement.ACKNOWLEDGEMENTS,
            "Lo-2ftdb7": StructuralElement.INTRODUCTION,
        }

    def test_acknowledgements_heading_resolves(self) -> None:
        """The Acknowledgements heading's element-type tag resolves to ACKNOWLEDGEMENTS via find + coerce."""
        heading = next(v for v in VertexTreeDFSIterator(_article6_vertex_tree()) if v.uid == "dpoX6c0Pl")
        assignment = find_guffin_attribute(heading, GuffinSemantics.ELEMENT_TYPE)
        assert assignment is not None
        assert element_type_of(assignment) is StructuralElement.ACKNOWLEDGEMENTS
