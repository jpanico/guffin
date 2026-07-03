"""Tests for guffin.model.guffin_semantics."""

import logging

import pytest
import yaml
from conftest import FIXTURES_YAML_DIR
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
    all_attributes_anchored,
    all_element_type_values_legal,
    all_matter_tags_at_section_level,
    all_matter_values_legal,
    element_type_of,
    element_type_of_vertex,
    find_guffin_attribute,
    has_parts,
    matter_of,
    matter_of_vertex,
    resolved_matter,
    validate_semantics,
)
from guffin.model.link import VertexLink, VertexLinkKind
from guffin.model.vertex import HeadingVertex, PageVertex, vertex_adapter
from guffin.model.vertex_tree import VertexTree, VertexTreeDFSIterator

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


class TestGuffinSemanticsMembers:
    """The GuffinSemantics vocabulary partitions into page-anchored metadata and heading tags."""

    def test_page_anchored_metadata_members(self) -> None:
        """The document-metadata members are page-anchored and carry their attribute names."""
        page_members = {m.value.name for m in GuffinSemantics if m.value.anchor is Anchor.PAGE}
        assert page_members == {"title", "subtitle", "authors", "date", "publisher", "rights", "identifier"}

    def test_heading_anchored_tag_members(self) -> None:
        """The heading-tag members are heading-anchored."""
        heading_members = {m.value.name for m in GuffinSemantics if m.value.anchor is Anchor.HEADING}
        assert heading_members == {"element-type", "matter"}


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
            "dpoX6c0Pl": StructuralElement.ACKNOWLEDGMENTS,
            "Lo-2ftdb7": StructuralElement.INTRODUCTION,
            "lSrjeyDaT": StructuralElement.PART,
            "tljWl5ZoV": StructuralElement.CHAPTER,
            "lZKsMSgZX": StructuralElement.PART,
            "oF7Lczujl": StructuralElement.PART,
            "MGvH7SY4M": StructuralElement.PART,
        }

    def test_acknowledgments_heading_resolves(self) -> None:
        """The Acknowledgements heading's element-type tag resolves to ACKNOWLEDGMENTS via find + coerce."""
        heading = next(v for v in VertexTreeDFSIterator(_article6_vertex_tree()) if v.uid == "dpoX6c0Pl")
        assignment = find_guffin_attribute(heading, GuffinSemantics.ELEMENT_TYPE)
        assert assignment is not None
        assert element_type_of(assignment) is StructuralElement.ACKNOWLEDGMENTS


class TestValidateSemanticsArticle6Fixture:
    """validate_semantics passes the real, tag-rich [[Test Article]] 6 fixture."""

    def test_fixture_is_semantically_valid(self) -> None:
        """The fixture's guffin-meta metadata, element-type tags, and matter tag all validate cleanly."""
        tree = _article6_vertex_tree()
        # Precondition: the fixture actually exercises the vocabulary, so a pass is not vacuous.
        tagged = [
            vertex
            for vertex in VertexTreeDFSIterator(tree)
            if find_guffin_attribute(vertex, GuffinSemantics.ELEMENT_TYPE) is not None
            or find_guffin_attribute(vertex, GuffinSemantics.MATTER) is not None
        ]
        assert tagged, "fixture carries no vocabulary tags; regenerate it from [[Test Article]] 6"
        result = validate_semantics(tree)
        assert result.errors == ()
        assert result.is_valid


def _tagged_heading_tree(heading_level: int, element_type: str | None) -> VertexTree:
    """A page with one heading at *heading_level*, optionally tagged ``element-type:: <value>``."""
    page = PageVertex(uid="pageroot1", title="Doc", children=["head00001"])
    heading = HeadingVertex(
        uid="head00001",
        text="A Heading",
        heading_level=heading_level,
        attribute_assignments=[_assignment("element-type", element_type)] if element_type is not None else None,
    )
    return VertexTree(tree_vertices=[page, heading])


def _heading_with(assignments: list[AttributeAssignment] | None) -> HeadingVertex:
    """A level-1 heading carrying *assignments*."""
    return HeadingVertex(uid="head00001", text="A Heading", heading_level=1, attribute_assignments=assignments)


class TestElementTypeOfVertex:
    """element_type_of_vertex() resolves a heading's element-type tag, tolerating absence and junk."""

    def test_tagged_heading_resolves(self) -> None:
        """A heading tagged with a legal element-type resolves to its StructuralElement."""
        heading = _heading_with([_assignment("element-type", "chapter")])
        assert element_type_of_vertex(heading) is StructuralElement.CHAPTER

    def test_untagged_heading_is_none(self) -> None:
        """A heading with no element-type assignment resolves to None."""
        assert element_type_of_vertex(_heading_with(None)) is None

    def test_illegal_value_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """An illegal element-type value resolves to None and logs a warning."""
        heading = _heading_with([_assignment("element-type", "not-an-element")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.guffin_semantics"):
            assert element_type_of_vertex(heading) is None
        assert "ignoring element-type" in caplog.text


class TestMatterOfVertex:
    """matter_of_vertex() resolves a heading's bare matter tag, tolerating absence and junk."""

    def test_tagged_heading_resolves(self) -> None:
        """A heading tagged with a legal matter resolves to its Matter."""
        heading = _heading_with([_assignment("matter", "back-matter")])
        assert matter_of_vertex(heading) is Matter.BACK

    def test_untagged_heading_is_none(self) -> None:
        """A heading with no matter assignment resolves to None."""
        assert matter_of_vertex(_heading_with(None)) is None

    def test_illegal_value_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """An illegal matter value resolves to None and logs a warning."""
        heading = _heading_with([_assignment("matter", "middle-matter")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.guffin_semantics"):
            assert matter_of_vertex(heading) is None
        assert "ignoring matter" in caplog.text


class TestResolvedMatter:
    """resolved_matter() resolves a heading's division: a bare matter tag beats the element default."""

    def test_element_default_when_no_override(self) -> None:
        """Without a matter tag, the element-type's conventional placement resolves."""
        heading = _heading_with([_assignment("element-type", "acknowledgments")])
        assert resolved_matter(heading) is Matter.FRONT

    def test_bare_matter_alone_resolves(self) -> None:
        """A bare matter tag with no element-type resolves directly."""
        heading = _heading_with([_assignment("matter", "front-matter")])
        assert resolved_matter(heading) is Matter.FRONT

    def test_override_beats_element_default_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A disagreeing matter tag wins over the element's placement, logging the override."""
        heading = _heading_with([_assignment("element-type", "acknowledgments"), _assignment("matter", "back-matter")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.guffin_semantics"):
            assert resolved_matter(heading) is Matter.BACK
        assert "overrides its element-type" in caplog.text

    def test_agreeing_override_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """A matter tag agreeing with the element's placement resolves without an override warning."""
        heading = _heading_with([_assignment("element-type", "acknowledgments"), _assignment("matter", "front-matter")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.guffin_semantics"):
            assert resolved_matter(heading) is Matter.FRONT
        assert "overrides" not in caplog.text

    def test_untagged_heading_is_none(self) -> None:
        """A heading with neither tag resolves to no division."""
        assert resolved_matter(_heading_with(None)) is None


class TestHasParts:
    """Tests for has_parts()."""

    def test_level_1_part_heading_detected(self) -> None:
        """A level-1 heading tagged element-type:: part makes the tree a parts tree."""
        assert has_parts(_tagged_heading_tree(1, "part")) is True

    def test_level_1_non_part_element_type_is_not_parts(self) -> None:
        """A level-1 heading tagged with a different element type does not."""
        assert has_parts(_tagged_heading_tree(1, "chapter")) is False

    def test_part_tag_below_level_1_is_not_parts(self) -> None:
        """A part tag on a deeper heading does not make the tree a parts tree."""
        assert has_parts(_tagged_heading_tree(2, "part")) is False

    def test_untagged_headings_are_not_parts(self) -> None:
        """Headings without element-type tags leave the tree partless."""
        assert has_parts(_tagged_heading_tree(1, None)) is False

    def test_unrecognised_element_type_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A junk element-type value is ignored (warned), not raised."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.guffin_semantics"):
            assert has_parts(_tagged_heading_tree(1, "not-an-element")) is False
        assert "ignoring element-type" in caplog.text


def _attributed_tree(
    page_names: list[str],
    heading_names: list[str],
    domain: AttributeDomain,
    value: str = "some value",
    heading_level: int = 1,
    ref_heading_names: list[str] | None = None,
    with_part: bool = False,
) -> VertexTree:
    """A page + heading at *heading_level*, each carrying single-*value* assignments for the given names.

    When *ref_heading_names* is given, a stub heading (also at *heading_level*) carrying those
    assignments is added to ``ref_vertices``.  When *with_part* is set, a level-1 heading tagged
    ``element-type:: part`` is added, making the tree a parts book.
    """

    def _assignments(names: list[str]) -> list[AttributeAssignment] | None:
        return [_assignment(name, value, domain) for name in names] or None

    children = ["head00001"] + (["parthead1"] if with_part else [])
    page = PageVertex(uid="pageroot1", title="Doc", children=children, attribute_assignments=_assignments(page_names))
    heading = HeadingVertex(
        uid="head00001",
        text="A Heading",
        heading_level=heading_level,
        attribute_assignments=_assignments(heading_names),
    )
    tree_vertices: list[HeadingVertex | PageVertex] = [page, heading]
    if with_part:
        tree_vertices.append(
            HeadingVertex(
                uid="parthead1",
                text="Book I",
                heading_level=1,
                attribute_assignments=[_assignment("element-type", "part")],
            )
        )
    ref_vertices = (
        [
            HeadingVertex(
                uid="refhead01",
                text="Ref Heading",
                heading_level=heading_level,
                attribute_assignments=_assignments(ref_heading_names),
            )
        ]
        if ref_heading_names
        else []
    )
    return VertexTree(tree_vertices=tree_vertices, ref_vertices=ref_vertices)


class TestAllAttributesAnchored:
    """all_attributes_anchored() enforces the GuffinAttribute.anchor invariant across a tree."""

    def test_correctly_anchored_attributes_pass(self) -> None:
        """Page metadata on the page and heading tags on a heading produce no error."""
        tree = _attributed_tree(["title", "authors"], ["element-type", "matter"], AttributeDomain.GUFFIN)
        assert all_attributes_anchored(tree) is None

    def test_page_attribute_on_heading_is_reported(self) -> None:
        """A page-anchored guffin attribute declared on a heading is a violation."""
        tree = _attributed_tree([], ["publisher"], AttributeDomain.GUFFIN)
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'publisher' is page-anchored" in error.message
        assert "uid='head00001'" in error.message

    def test_heading_attribute_on_page_is_reported(self) -> None:
        """A heading-anchored guffin attribute declared on the page is a violation."""
        tree = _attributed_tree(["element-type"], [], AttributeDomain.GUFFIN)
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'element-type' is heading-anchored" in error.message
        assert "uid='pageroot1'" in error.message

    def test_all_violations_accumulate_into_one_error(self) -> None:
        """Multiple misanchored attributes are all listed in the single error message."""
        tree = _attributed_tree(["matter"], ["title", "rights"], AttributeDomain.GUFFIN)
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'matter'" in error.message
        assert "'title'" in error.message
        assert "'rights'" in error.message

    def test_default_domain_attributes_are_not_checked(self) -> None:
        """A default-domain attribute sharing a recognised name is outside the vocabulary."""
        tree = _attributed_tree([], ["title"], AttributeDomain.DEFAULT)
        assert all_attributes_anchored(tree) is None

    def test_unrecognised_guffin_names_are_not_checked(self) -> None:
        """A guffin-domain attribute with an unrecognised name is outside the vocabulary."""
        tree = _attributed_tree([], ["not-a-member"], AttributeDomain.GUFFIN)
        assert all_attributes_anchored(tree) is None

    def test_ref_vertices_are_checked(self) -> None:
        """A misanchored attribute on a referenced-vertex stub is also a violation."""
        tree = _attributed_tree([], [], AttributeDomain.GUFFIN, ref_heading_names=["publisher"])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "uid='refhead01'" in error.message


class TestAllElementTypeValuesLegal:
    """all_element_type_values_legal() rejects element-type values outside StructuralElement."""

    def test_legal_value_passes(self) -> None:
        """An element-type assignment naming a StructuralElement produces no error."""
        tree = _attributed_tree([], ["element-type"], AttributeDomain.GUFFIN, value="chapter")
        assert all_element_type_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """An element-type value outside StructuralElement is a violation naming the vertex."""
        tree = _attributed_tree([], ["element-type"], AttributeDomain.GUFFIN, value="not-an-element")
        error = all_element_type_values_legal(tree)
        assert error is not None
        assert "uid='head00001'" in error.message
        assert "not-an-element" in error.message

    def test_other_attributes_ignored(self) -> None:
        """Assignments for other attributes are outside this validator's scope."""
        tree = _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="bogus")
        assert all_element_type_values_legal(tree) is None

    def test_ref_vertices_are_checked(self) -> None:
        """An illegal element-type value on a referenced-vertex stub is also a violation."""
        tree = _attributed_tree(
            [], [], AttributeDomain.GUFFIN, value="not-an-element", ref_heading_names=["element-type"]
        )
        error = all_element_type_values_legal(tree)
        assert error is not None
        assert "uid='refhead01'" in error.message


class TestAllMatterValuesLegal:
    """all_matter_values_legal() rejects matter values outside Matter."""

    def test_legal_value_passes(self) -> None:
        """A matter assignment naming a Matter division produces no error."""
        tree = _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="front-matter")
        assert all_matter_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """A matter value outside Matter is a violation naming the vertex."""
        tree = _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="middle-matter")
        error = all_matter_values_legal(tree)
        assert error is not None
        assert "uid='head00001'" in error.message
        assert "middle-matter" in error.message

    def test_other_attributes_ignored(self) -> None:
        """Assignments for other attributes are outside this validator's scope."""
        tree = _attributed_tree([], ["element-type"], AttributeDomain.GUFFIN, value="bogus")
        assert all_matter_values_legal(tree) is None

    def test_ref_vertices_are_checked(self) -> None:
        """An illegal matter value on a referenced-vertex stub is also a violation."""
        tree = _attributed_tree([], [], AttributeDomain.GUFFIN, value="middle-matter", ref_heading_names=["matter"])
        error = all_matter_values_legal(tree)
        assert error is not None
        assert "uid='refhead01'" in error.message


class TestAllMatterTagsAtSectionLevel:
    """all_matter_tags_at_section_level() restricts matter tags to the book's section level."""

    def test_chapters_book_matter_on_level_1_passes(self) -> None:
        """In a chapters book (no parts), a matter tag on a level-1 heading produces no error."""
        tree = _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="front-matter")
        assert all_matter_tags_at_section_level(tree) is None

    def test_chapters_book_matter_on_level_2_reported(self) -> None:
        """In a chapters book, a matter tag on a level-2 heading is a violation naming the vertex."""
        tree = _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="front-matter", heading_level=2)
        error = all_matter_tags_at_section_level(tree)
        assert error is not None
        assert "level-2" in error.message
        assert "chapters book" in error.message
        assert "uid='head00001'" in error.message

    def test_parts_book_matter_on_level_2_passes(self) -> None:
        """In a parts book, sections live at level 2, so a matter tag there produces no error."""
        tree = _attributed_tree(
            [], ["matter"], AttributeDomain.GUFFIN, value="front-matter", heading_level=2, with_part=True
        )
        assert all_matter_tags_at_section_level(tree) is None

    def test_parts_book_matter_on_level_1_reported(self) -> None:
        """In a parts book, level 1 is the part layer, so a matter tag there is a violation."""
        tree = _attributed_tree(
            [], ["matter"], AttributeDomain.GUFFIN, value="front-matter", heading_level=1, with_part=True
        )
        error = all_matter_tags_at_section_level(tree)
        assert error is not None
        assert "level-1" in error.message
        assert "parts book" in error.message
        assert "uid='head00001'" in error.message

    def test_matter_on_non_heading_left_to_anchor_validator(self) -> None:
        """A matter tag on the page is the anchor validator's concern, not this one's."""
        tree = _attributed_tree(["matter"], [], AttributeDomain.GUFFIN, value="front-matter")
        assert all_matter_tags_at_section_level(tree) is None

    def test_ref_vertices_are_checked(self) -> None:
        """A matter tag on a misleveled referenced-stub heading is also a violation."""
        tree = _attributed_tree(
            [], [], AttributeDomain.GUFFIN, value="front-matter", heading_level=2, ref_heading_names=["matter"]
        )
        error = all_matter_tags_at_section_level(tree)
        assert error is not None
        assert "uid='refhead01'" in error.message


class TestValidateSemantics:
    """validate_semantics() accumulates the vocabulary validators into a ValidationResult."""

    def test_valid_tree_yields_valid_result(self) -> None:
        """A correctly tagged tree validates cleanly."""
        tree = _attributed_tree(["title"], ["element-type"], AttributeDomain.GUFFIN, value="chapter")
        assert validate_semantics(tree).is_valid

    def test_misanchored_tree_yields_error(self) -> None:
        """A misanchored attribute surfaces as a ValidationError in the result."""
        result = validate_semantics(_attributed_tree(["matter"], [], AttributeDomain.GUFFIN, value="front-matter"))
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "misanchored guffin attributes" in result.errors[0].message

    def test_violations_accumulate_across_validators(self) -> None:
        """Distinct invariant violations each surface as their own ValidationError."""
        # An illegal matter value on a level-2 heading violates two invariants at once.
        result = validate_semantics(
            _attributed_tree([], ["matter"], AttributeDomain.GUFFIN, value="middle-matter", heading_level=2)
        )
        assert not result.is_valid
        assert len(result.errors) == 2
        messages = " | ".join(error.message for error in result.errors)
        assert "illegal matter values" in messages
        assert "misplaced matter tags" in messages
