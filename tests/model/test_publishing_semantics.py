"""Tests for guffin.model.publishing_semantics."""

import logging

import pytest
import yaml
from conftest import FIXTURES_YAML_DIR
from pydantic import ValidationError

from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
)
from guffin.model.attribute_anchor import AttributeAnchor
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.chicago_structure import Matter, StructuralElement
from guffin.model.publishing_semantics import (
    DEFAULT_PDF_RENDER,
    DEFAULT_PUBLISH,
    PdfRender,
    PublishingAttribute,
    PublishingSemantics,
    _anchor_mismatch,
    all_attributes_anchored,
    all_element_type_values_legal,
    all_matter_tags_at_section_level,
    all_matter_values_legal,
    all_pdf_render_values_legal,
    all_publish_values_legal,
    drop_unpublished,
    element_type_of,
    element_type_of_vertex,
    find_publishing_attribute,
    has_element_type,
    has_parts,
    matter_of,
    matter_of_vertex,
    pdf_render_of,
    pdf_render_of_vertex,
    publish_of,
    publish_of_vertex,
    resolved_matter,
    validate_semantics,
)
from guffin.model.vertex import (
    BlockEmbedVertex,
    HeadingVertex,
    PageVertex,
    PdfVertex,
    TextVertex,
    vertex_adapter,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree, VertexTreeDFSIterator

_LINK = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")


def _assignment(name: str, value: str, domain: AttributeDomain = AttributeDomain.GUFFIN) -> AttributeAssignment:
    """Build a single-value AttributeAssignment for attribute *name* in *domain* carrying *value*."""
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=name, domain=domain), link=_LINK),
        values=(LiteralValue(value=value),),
    )


class TestPublishingAttribute:
    """PublishingAttribute pins its domain to GUFFIN and requires an anchor."""

    def test_domain_defaults_to_guffin(self) -> None:
        """The domain is the guffin domain without being passed."""
        attribute = PublishingAttribute(name="title", anchor=AttributeAnchor.PAGE)
        assert attribute.domain is AttributeDomain.GUFFIN

    def test_non_guffin_domain_is_rejected(self) -> None:
        """Constructing with any domain other than GUFFIN raises."""
        with pytest.raises(ValidationError):
            PublishingAttribute(name="x", anchor=AttributeAnchor.PAGE, domain=AttributeDomain.DEFAULT)

    def test_anchor_is_required(self) -> None:
        """Constructing without an anchor raises."""
        with pytest.raises(ValidationError):
            PublishingAttribute(name="x")  # type: ignore[call-arg]


class TestPublishingSemanticsMembers:
    """The PublishingSemantics vocabulary partitions into root-anchored metadata and per-vertex tags."""

    def test_root_anchored_metadata_members(self) -> None:
        """The document-metadata members are root-anchored and carry their attribute names."""
        root_members = {m.value.name for m in PublishingSemantics if m.value.anchor is AttributeAnchor.ROOT}
        assert root_members == {"title", "subtitle", "authors", "date", "publisher", "rights", "identifier"}

    def test_heading_anchored_tag_members(self) -> None:
        """The heading-tag members are heading-anchored."""
        heading_members = {m.value.name for m in PublishingSemantics if m.value.anchor is AttributeAnchor.HEADING}
        assert heading_members == {"element-type", "matter"}

    def test_pdf_anchored_tag_members(self) -> None:
        """The PDF-tag members are pdf-anchored."""
        pdf_members = {m.value.name for m in PublishingSemantics if m.value.anchor is AttributeAnchor.PDF}
        assert pdf_members == {"pdf-render"}


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
            if (assignment := find_publishing_attribute(vertex, PublishingSemantics.ELEMENT_TYPE)) is not None
        }
        assert resolved == {
            "dpoX6c0Pl": StructuralElement.ACKNOWLEDGMENTS,
            "Lo-2ftdb7": StructuralElement.INTRODUCTION,
            "lSrjeyDaT": StructuralElement.PART,
            "tljWl5ZoV": StructuralElement.CHAPTER,
            "LZJSmETBX": StructuralElement.CHAPTER,
            "a2cA9YFVP": StructuralElement.CHAPTER,
            "N-SyzJ3ai": StructuralElement.CHAPTER,
            "L0xspxsKt": StructuralElement.CHAPTER,
            "lZKsMSgZX": StructuralElement.PART,
            "oF7Lczujl": StructuralElement.PART,
            "MGvH7SY4M": StructuralElement.PART,
        }

    def test_acknowledgments_heading_resolves(self) -> None:
        """The Acknowledgements heading's element-type tag resolves to ACKNOWLEDGMENTS via find + coerce."""
        heading = next(v for v in VertexTreeDFSIterator(_article6_vertex_tree()) if v.uid == "dpoX6c0Pl")
        assignment = find_publishing_attribute(heading, PublishingSemantics.ELEMENT_TYPE)
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
            if find_publishing_attribute(vertex, PublishingSemantics.ELEMENT_TYPE) is not None
            or find_publishing_attribute(vertex, PublishingSemantics.MATTER) is not None
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


_PDF_URL = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf?alt=media&token=aaa"


def _pdf_with(assignments: list[AttributeAssignment] | None) -> PdfVertex:
    """A PDF vertex carrying *assignments*."""
    return PdfVertex(uid="pdfuid001", source=_PDF_URL, attribute_assignments=assignments)  # type: ignore[arg-type]


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
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
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
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
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
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert resolved_matter(heading) is Matter.BACK
        assert "overrides its element-type" in caplog.text

    def test_agreeing_override_does_not_warn(self, caplog: pytest.LogCaptureFixture) -> None:
        """A matter tag agreeing with the element's placement resolves without an override warning."""
        heading = _heading_with([_assignment("element-type", "acknowledgments"), _assignment("matter", "front-matter")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert resolved_matter(heading) is Matter.FRONT
        assert "overrides" not in caplog.text

    def test_untagged_heading_is_none(self) -> None:
        """A heading with neither tag resolves to no division."""
        assert resolved_matter(_heading_with(None)) is None


class TestPdfRenderOf:
    """pdf_render_of validates the attribute identity and coerces the value to a PdfRender."""

    def test_returns_named_pdf_render(self) -> None:
        """A valid pdf-render assignment yields the named PdfRender."""
        assert pdf_render_of(_assignment("pdf-render", "inline")) is PdfRender.INLINE

    def test_wrong_attribute_name_rejected(self) -> None:
        """An assignment for a different attribute raises, even with a valid pdf-render value."""
        with pytest.raises(ValueError):
            pdf_render_of(_assignment("matter", "inline"))

    def test_unknown_value_rejected(self) -> None:
        """A value that is not a recognised PdfRender raises."""
        with pytest.raises(ValueError):
            pdf_render_of(_assignment("pdf-render", "thumbnail"))


class TestPdfRenderOfVertex:
    """pdf_render_of_vertex() resolves a PDF embed's pdf-render tag, tolerating absence and junk."""

    def test_inline_tag_resolves(self) -> None:
        """A pdf-render:: inline tag resolves to INLINE."""
        assert pdf_render_of_vertex(_pdf_with([_assignment("pdf-render", "inline")])) is PdfRender.INLINE

    def test_link_tag_resolves(self) -> None:
        """A pdf-render:: link tag resolves to LINK."""
        assert pdf_render_of_vertex(_pdf_with([_assignment("pdf-render", "link")])) is PdfRender.LINK

    def test_untagged_is_none_and_default_is_link(self) -> None:
        """An untagged PDF resolves to None; the vocabulary default placement is LINK."""
        assert pdf_render_of_vertex(_pdf_with(None)) is None
        assert DEFAULT_PDF_RENDER is PdfRender.LINK

    def test_illegal_value_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A junk pdf-render value is ignored (warned), not raised."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert pdf_render_of_vertex(_pdf_with([_assignment("pdf-render", "sideways")])) is None
        assert "ignoring pdf-render" in caplog.text


class TestAllPdfRenderValuesLegal:
    """all_pdf_render_values_legal() rejects unrecognised pdf-render values across a tree."""

    def test_legal_value_passes(self) -> None:
        """A tree whose pdf-render values are all recognised produces no error."""
        tree = VertexTree(tree_vertices=[_pdf_with([_assignment("pdf-render", "inline")])])
        assert all_pdf_render_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """An unrecognised pdf-render value is reported with the vertex uid."""
        tree = VertexTree(tree_vertices=[_pdf_with([_assignment("pdf-render", "thumbnail")])])
        error = all_pdf_render_values_legal(tree)
        assert error is not None
        assert "pdfuid001" in error.message

    def test_pdf_render_on_heading_reported_by_anchor_validator(self) -> None:
        """A pdf-render tag on a heading is a misanchoring, caught by all_attributes_anchored."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("pdf-render", "inline")])])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "pdf-render" in error.message


class TestFindPublishingAttribute:
    """find_publishing_attribute() requires an actual PublishingSemantics member (strict validation)."""

    def test_member_finds_assignment(self) -> None:
        """A vertex carrying the member's attribute yields the assignment."""
        heading = _heading_with([_assignment("element-type", "chapter")])
        assignment = find_publishing_attribute(heading, PublishingSemantics.ELEMENT_TYPE)
        assert assignment is not None
        assert assignment.attribute.definition.name == "element-type"

    def test_member_payload_is_rejected(self) -> None:
        """The member's PublishingAttribute payload is not coerced by value — members only."""
        heading = _heading_with(None)
        with pytest.raises(ValidationError):
            find_publishing_attribute(heading, PublishingSemantics.ELEMENT_TYPE.value)  # type: ignore[arg-type]

    def test_identity_equal_attribute_is_rejected(self) -> None:
        """A bare Attribute carrying a member's identity (equal under identity-equality) is rejected."""
        heading = _heading_with(None)
        impostor = Attribute(name="element-type", domain=AttributeDomain.GUFFIN)
        with pytest.raises(ValidationError):
            find_publishing_attribute(heading, impostor)  # type: ignore[arg-type]


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
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert has_parts(_tagged_heading_tree(1, "not-an-element")) is False
        assert "ignoring element-type" in caplog.text

    def test_part_heading_transcluded_via_embed_detected(self) -> None:
        """A part heading pulled in through a block embed structures the rendered document as parts."""
        page = PageVertex(uid="pageroot1", title="Book", children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="parthead1"))
        part_heading = HeadingVertex(
            uid="parthead1",
            text="Part One",
            heading_level=1,
            attribute_assignments=[_assignment("element-type", "part")],
        )
        tree = VertexTree(tree_vertices=[page, embed], ref_vertices=[part_heading])
        assert has_parts(tree) is True

    def test_part_heading_merely_referenced_is_not_parts(self) -> None:
        """A part heading that is only mentioned (rendered inline as text) does not make parts."""
        page = PageVertex(uid="pageroot1", title="Book", refs=["parthead1"])
        part_heading = HeadingVertex(
            uid="parthead1",
            text="Part One",
            heading_level=1,
            attribute_assignments=[_assignment("element-type", "part")],
        )
        tree = VertexTree(tree_vertices=[page], ref_vertices=[part_heading])
        assert has_parts(tree) is False


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
    """all_attributes_anchored() enforces the PublishingAttribute.anchor invariant across a tree."""

    def test_correctly_anchored_attributes_pass(self) -> None:
        """Page metadata on the page and heading tags on a heading produce no error."""
        tree = _attributed_tree(["title", "authors"], ["element-type", "matter"], AttributeDomain.GUFFIN)
        assert all_attributes_anchored(tree) is None

    def test_metadata_on_non_root_vertex_is_reported(self) -> None:
        """A root-anchored metadata attribute declared below the root is a positional violation."""
        tree = _attributed_tree([], ["publisher"], AttributeDomain.GUFFIN)
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'publisher' is root-anchored" in error.message
        assert "non-root vertex" in error.message
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

    def test_embed_transcluded_part_makes_level_2_the_section_level(self) -> None:
        """Parts-ness carried in through a block embed sets the section level to 2 for matter tags."""
        page = PageVertex(uid="pageroot1", title="Book", children=["embed0001", "head00001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="parthead1"))
        part_heading = HeadingVertex(
            uid="parthead1",
            text="Part One",
            heading_level=1,
            attribute_assignments=[_assignment("element-type", "part")],
        )
        matter_heading = HeadingVertex(
            uid="head00001",
            text="Preface",
            heading_level=2,
            attribute_assignments=[_assignment("matter", "front-matter")],
        )
        tree = VertexTree(tree_vertices=[page, embed, matter_heading], ref_vertices=[part_heading])
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


class TestAnchorMismatch:
    """_anchor_mismatch() checks both anchor axes: vertex type and tree position."""

    def test_root_anchored_on_root_vertex_passes(self) -> None:
        """A root-anchored attribute on the root vertex satisfies the anchor."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        root = PageVertex(uid="pageroot1", title="Doc")
        assert _anchor_mismatch(attribute, root, "pageroot1") is None

    def test_root_anchored_on_non_page_root_passes(self) -> None:
        """The root anchor is type-independent: a heading root (subtree export) also satisfies it."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        root = HeadingVertex(uid="head00001", text="H", heading_level=1)
        assert _anchor_mismatch(attribute, root, "head00001") is None

    def test_root_anchored_on_non_root_vertex_is_reported(self) -> None:
        """A root-anchored attribute anywhere but the root is a positional mismatch."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        stray = TextVertex(uid="txt00001a", text="hello")
        mismatch = _anchor_mismatch(attribute, stray, "pageroot1")
        assert mismatch is not None
        assert "root-anchored" in mismatch
        assert "non-root vertex" in mismatch
        assert "uid='txt00001a'" in mismatch

    def test_type_mismatch_reported_before_position(self) -> None:
        """A vertex failing the type axis reports the type mismatch."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.HEADING)
        stray = TextVertex(uid="txt00001a", text="hello")
        mismatch = _anchor_mismatch(attribute, stray, "pageroot1")
        assert mismatch is not None
        assert "heading-anchored" in mismatch


class TestPublishOf:
    """publish_of() reads a publish assignment's sole value as a boolean."""

    def test_false_literal(self) -> None:
        """'false' names the unpublished state."""
        assert publish_of(_assignment("publish", "false")) is False

    def test_true_literal(self) -> None:
        """'true' names the published state."""
        assert publish_of(_assignment("publish", "true")) is True

    def test_rejects_wrong_attribute(self) -> None:
        """An assignment for a different attribute is rejected."""
        with pytest.raises(ValueError, match="publish"):
            publish_of(_assignment("matter", "false"))

    def test_rejects_non_boolean_literal(self) -> None:
        """A value that is neither 'true' nor 'false' is rejected."""
        with pytest.raises(ValueError, match="'maybe'"):
            publish_of(_assignment("publish", "maybe"))


class TestPublishOfVertex:
    """publish_of_vertex() resolves a vertex's publish tag, tolerating absence and bad values."""

    def test_tagged_vertex_resolves(self) -> None:
        """A tagged heading resolves to its declared state."""
        heading = _heading_with([_assignment("publish", "false")])
        assert publish_of_vertex(heading) is False

    def test_untagged_vertex_is_none(self) -> None:
        """An untagged vertex resolves to None (DEFAULT_PUBLISH applies)."""
        assert publish_of_vertex(_heading_with(None)) is None
        assert DEFAULT_PUBLISH is True

    def test_illegal_value_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A non-boolean value is ignored with a warning."""
        heading = _heading_with([_assignment("publish", "maybe")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert publish_of_vertex(heading) is None
        assert any("ignoring publish" in record.message for record in caplog.records)


class TestAllPublishValuesLegal:
    """all_publish_values_legal() requires every publish value to be a boolean literal."""

    def test_legal_values_pass(self) -> None:
        """'true'/'false' values produce no error."""
        tree = _attributed_tree([], ["publish"], AttributeDomain.GUFFIN, value="false")
        assert all_publish_values_legal(tree) is None

    def test_illegal_value_is_reported(self) -> None:
        """A non-boolean publish value is a violation."""
        tree = _attributed_tree([], ["publish"], AttributeDomain.GUFFIN, value="maybe")
        error = all_publish_values_legal(tree)
        assert error is not None
        assert "illegal publish values" in error.message
        assert "uid='head00001'" in error.message

    def test_publish_on_page_is_misanchored(self) -> None:
        """A publish tag on a page vertex is reported by the anchor validator."""
        tree = _attributed_tree(["publish"], [], AttributeDomain.GUFFIN, value="false")
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'publish' is block-anchored" in error.message


def _text_vertex(uid: str, children: list[str] | None = None, publish: str | None = None) -> TextVertex:
    """Build a TextVertex, optionally with children and a publish tag."""
    return TextVertex(
        uid=uid,
        text=f"text {uid}",
        children=children,
        attribute_assignments=[_assignment("publish", publish)] if publish is not None else None,
    )


class TestDropUnpublished:
    """drop_unpublished() prunes publish:: false subtrees, embeds of pruned content included."""

    def test_untagged_tree_passes_through(self) -> None:
        """A tree with no publish tags is returned unchanged (the same object)."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001"])
        tree = VertexTree(tree_vertices=[root, _text_vertex("keep00001")])
        assert drop_unpublished(tree) is tree

    def test_tagged_subtree_is_pruned(self) -> None:
        """A tagged vertex vanishes with its descendants, and the parent's children list is stripped."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001", "drop00001"])
        drop = _text_vertex("drop00001", children=["nest00001"], publish="false")
        tree = VertexTree(
            tree_vertices=[root, _text_vertex("keep00001"), drop, _text_vertex("nest00001")],
        )
        pruned = drop_unpublished(tree)
        assert [vtx.uid for vtx in pruned.tree_vertices] == ["pageroot1", "keep00001"]
        assert pruned.uid_map["pageroot1"].children == ["keep00001"]

    def test_publish_true_is_kept(self) -> None:
        """An explicit publish:: true is the same as untagged: nothing is pruned."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001"])
        tree = VertexTree(tree_vertices=[root, _text_vertex("keep00001", publish="true")])
        assert drop_unpublished(tree) is tree

    def test_embed_of_unpublished_target_vanishes(self) -> None:
        """A block embed whose transclusion target is unpublished is pruned with it."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001", "embd00001"])
        embed = BlockEmbedVertex(uid="embd00001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="reftgt001"))
        target = _text_vertex("reftgt001", publish="false")
        tree = VertexTree(tree_vertices=[root, _text_vertex("keep00001"), embed], ref_vertices=[target])
        pruned = drop_unpublished(tree)
        assert [vtx.uid for vtx in pruned.tree_vertices] == ["pageroot1", "keep00001"]
        assert pruned.ref_vertices == []
        assert pruned.uid_map["pageroot1"].children == ["keep00001"]

    def test_illegal_value_prunes_nothing(self) -> None:
        """A vertex whose publish value is not a boolean stays published (tolerant reader)."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001"])
        tree = VertexTree(tree_vertices=[root, _text_vertex("keep00001", publish="maybe")])
        assert drop_unpublished(tree) is tree

    def test_unpublished_root_raises(self) -> None:
        """An export target tagged publish:: false is rejected outright."""
        root = HeadingVertex(
            uid="head00001",
            text="A Heading",
            heading_level=1,
            attribute_assignments=[_assignment("publish", "false")],
        )
        tree = VertexTree(tree_vertices=[root])
        with pytest.raises(ValueError, match="export target"):
            drop_unpublished(tree)


class TestHasElementType:
    """has_element_type() detects a render-visible heading tagged with a given StructuralElement."""

    def test_tagged_heading_found(self) -> None:
        """A heading tagged with the sought element is found."""
        tree = _tagged_heading_tree(1, "table-of-contents")
        assert has_element_type(tree, StructuralElement.TABLE_OF_CONTENTS)

    def test_other_element_not_matched(self) -> None:
        """A heading tagged with a different element does not match."""
        tree = _tagged_heading_tree(1, "chapter")
        assert not has_element_type(tree, StructuralElement.TABLE_OF_CONTENTS)

    def test_untagged_tree_is_false(self) -> None:
        """A tree with no element-type tags matches nothing."""
        tree = _tagged_heading_tree(1, None)
        assert not has_element_type(tree, StructuralElement.TABLE_OF_CONTENTS)
