"""Tests for guffin.model.publishing_validation."""

import yaml
from conftest import FIXTURES_YAML_DIR
from pydantic import HttpUrl

from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
)
from guffin.model.attribute_anchor import AttributeAnchor
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.publishing_semantics import (
    PublishingAttribute,
    PublishingSemantics,
    find_publishing_attribute,
)
from guffin.model.publishing_validation import (
    _anchor_mismatch,
    all_attributes_anchored,
    all_code_language_values_legal,
    all_code_source_values_legal,
    all_cover_image_values_legal,
    all_date_values_legal,
    all_element_number_matters_agree,
    all_element_number_matters_legal,
    all_element_numbers_in_headings_only,
    all_element_numbers_nested,
    all_element_numbers_ordered,
    all_element_numbers_unique,
    all_element_numbers_well_formed,
    all_element_type_values_legal,
    all_matter_tags_at_section_level,
    all_matter_values_legal,
    all_pdf_render_values_legal,
    all_publish_values_legal,
    validate_semantics,
)
from guffin.model.vertex import (
    BlockEmbedVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
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


def _multi_assignment(name: str, *values: str) -> AttributeAssignment:
    """Build a guffin-domain AttributeAssignment for attribute *name* carrying *values* in order."""
    return AttributeAssignment(
        attribute=AttributeInstance(definition=Attribute(name=name, domain=AttributeDomain.GUFFIN), link=_LINK),
        values=tuple(LiteralValue(value=value) for value in values),
    )


def _article7_vertex_tree() -> VertexTree:
    """Load the [[Test Article]] 7 VertexTree from its YAML fixture."""
    raw = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_7_vertices.yaml").read_text())
    return VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])


def _heading_with(assignments: list[AttributeAssignment] | None) -> HeadingVertex:
    """A level-1 heading carrying *assignments*."""
    return HeadingVertex(uid="head00001", text="A Heading", heading_level=1, attribute_assignments=assignments)


_PDF_URL = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf?alt=media&token=aaa"


def _pdf_with(assignments: list[AttributeAssignment] | None) -> PdfVertex:
    """A PDF vertex carrying *assignments*."""
    return PdfVertex(uid="pdfuid001", source=_PDF_URL, attribute_assignments=assignments)  # type: ignore[arg-type]


def _code_block_with(assignments: list[AttributeAssignment] | None) -> CodeBlockVertex:
    """A python code-block vertex carrying *assignments*."""
    return CodeBlockVertex(uid="codeuid01", code="print(1)", language="python", attribute_assignments=assignments)


_SOURCE_URL = "https://github.com/psf/requests/blob/main/src/requests/api.py#L14-L60"
_SOURCE_SHA = "0d9ca427f7d7dbe92694284d4a6249178255036e"
_SOURCE_DATE = "2026-07-17"


def _code_source_assignment(
    url: str = _SOURCE_URL, sha: str = _SOURCE_SHA, date: str = _SOURCE_DATE
) -> AttributeAssignment:
    """Build a three-valued code-source assignment (url, commit sha, fetched date)."""
    return _multi_assignment("code-source", url, sha, date)


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
    assignments is added to ``ref_vertices`` and transcluded into the document through a block embed
    (so it is part of the render-visible document that the guffin validators check).  When *with_part*
    is set, a level-1 heading tagged ``element-type:: part`` is added, making the tree a parts book.
    """

    def _assignments(names: list[str]) -> list[AttributeAssignment] | None:
        return [_assignment(name, value, domain) for name in names] or None

    children = ["head00001"] + (["parthead1"] if with_part else []) + (["refembed1"] if ref_heading_names else [])
    page = PageVertex(uid="pageroot1", title="Doc", children=children, attribute_assignments=_assignments(page_names))
    heading = HeadingVertex(
        uid="head00001",
        text="A Heading",
        heading_level=heading_level,
        attribute_assignments=_assignments(heading_names),
    )
    tree_vertices: list[HeadingVertex | PageVertex | BlockEmbedVertex] = [page, heading]
    if with_part:
        tree_vertices.append(
            HeadingVertex(
                uid="parthead1",
                text="Book I",
                heading_level=1,
                attribute_assignments=[_assignment("element-type", "part")],
            )
        )
    if ref_heading_names:
        tree_vertices.append(
            BlockEmbedVertex(uid="refembed1", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="refhead01"))
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


def _cover_image_vertex_fixture(target_uid: str = "imgcover1") -> ImageVertex:
    """An ImageVertex standing in for a referenced cover image block."""
    return ImageVertex(
        uid=target_uid,
        source=HttpUrl("https://firebasestorage.googleapis.com/v0/b/t/o/imgs%2Fcover.jpeg?alt=media&token=cov1"),
        media_type=MediaType.JPEG,
        scaled_image_size=ImageSize(),
    )


def _covered_tree(value: str = "((imgcover1))", with_image: bool = True) -> VertexTree:
    """A page root carrying a cover-image assignment, with the referenced image among the refs."""
    page = PageVertex(uid="pageroot1", title="Doc", attribute_assignments=[_assignment("cover-image", value)])
    refs = [_cover_image_vertex_fixture()] if with_image else []
    return VertexTree(tree_vertices=[page], ref_vertices=refs)


def _flat_headed_tree(*headings: tuple[str, str]) -> VertexTree:
    """A page whose children are level-1 headings, given as (uid, text) pairs in document order."""
    page = PageVertex(uid="pageroot1", title="Doc", children=[uid for uid, _text in headings])
    vertices = [HeadingVertex(uid=uid, text=text, heading_level=1) for uid, text in headings]
    return VertexTree(tree_vertices=[page, *vertices])


class TestValidateSemanticsArticle7Fixture:
    """validate_semantics passes the real, tag-rich [[Test Article]] 7 fixture."""

    def test_fixture_is_semantically_valid(self) -> None:
        """The fixture's guffin-meta metadata, element-type tags, and matter tag all validate cleanly."""
        tree = _article7_vertex_tree()
        # Precondition: the fixture actually exercises the vocabulary, so a pass is not vacuous.
        tagged = [
            vertex
            for vertex in VertexTreeDFSIterator(tree)
            if find_publishing_attribute(vertex, PublishingSemantics.ELEMENT_TYPE) is not None
            or find_publishing_attribute(vertex, PublishingSemantics.MATTER) is not None
        ]
        assert tagged, "fixture carries no vocabulary tags; regenerate it from [[Test Article]] 7"
        result = validate_semantics(tree)
        assert result.errors == ()
        assert result.is_valid


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


class TestAllCodeLanguageValuesLegal:
    """all_code_language_values_legal() rejects unresolvable code-language values across a tree."""

    def test_legal_value_passes(self) -> None:
        """A tree whose code-language values all resolve produces no error."""
        tree = VertexTree(tree_vertices=[_code_block_with([_assignment("code-language", "fortran")])])
        assert all_code_language_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """An unresolvable code-language value is reported with the vertex uid."""
        tree = VertexTree(tree_vertices=[_code_block_with([_assignment("code-language", "edsac")])])
        error = all_code_language_values_legal(tree)
        assert error is not None
        assert "codeuid01" in error.message

    def test_code_language_on_heading_reported_by_anchor_validator(self) -> None:
        """A code-language tag on a heading is a misanchoring, caught by all_attributes_anchored."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("code-language", "fortran")])])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "code-language" in error.message


class TestAllCodeSourceValuesLegal:
    """all_code_source_values_legal() rejects malformed code-source triples across a tree."""

    def test_legal_triple_passes(self) -> None:
        """A tree whose code-source triples all parse produces no error."""
        tree = VertexTree(tree_vertices=[_code_block_with([_code_source_assignment()])])
        assert all_code_source_values_legal(tree) is None

    def test_illegal_triple_reported(self) -> None:
        """A malformed code-source value is reported with the vertex uid."""
        tree = VertexTree(tree_vertices=[_code_block_with([_code_source_assignment(date="July 17")])])
        error = all_code_source_values_legal(tree)
        assert error is not None
        assert "codeuid01" in error.message

    def test_wrong_arity_reported(self) -> None:
        """A two-valued code-source assignment is reported."""
        tree = VertexTree(
            tree_vertices=[_code_block_with([_multi_assignment("code-source", _SOURCE_URL, _SOURCE_SHA)])]
        )
        error = all_code_source_values_legal(tree)
        assert error is not None
        assert "3 values" in error.message

    def test_code_source_on_heading_reported_by_anchor_validator(self) -> None:
        """A code-source tag on a heading is a misanchoring, caught by all_attributes_anchored."""
        tree = VertexTree(tree_vertices=[_heading_with([_code_source_assignment()])])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "code-source" in error.message


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

    def test_embed_transcluded_ref_vertices_are_checked(self) -> None:
        """A misanchored attribute on an embed-transcluded referenced vertex is also a violation."""
        tree = _attributed_tree([], [], AttributeDomain.GUFFIN, ref_heading_names=["publisher"])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "uid='refhead01'" in error.message

    def test_mention_only_ref_vertices_are_not_checked(self) -> None:
        """A misanchored attribute on a merely-mentioned ref vertex (not transcluded) is not checked."""
        heading = HeadingVertex(
            uid="refhead01",
            text="Ref Heading",
            heading_level=1,
            attribute_assignments=[_assignment("publisher", "some value", AttributeDomain.GUFFIN)],
        )
        page = PageVertex(uid="pageroot1", title="Doc", refs=["refhead01"])
        tree = VertexTree(tree_vertices=[page], ref_vertices=[heading])
        assert all_attributes_anchored(tree) is None


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

    def test_embed_transcluded_ref_vertices_are_checked(self) -> None:
        """An illegal element-type value on an embed-transcluded referenced vertex is also a violation."""
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

    def test_embed_transcluded_ref_vertices_are_checked(self) -> None:
        """An illegal matter value on an embed-transcluded referenced vertex is also a violation."""
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

    def test_embed_transcluded_ref_vertices_are_checked(self) -> None:
        """A matter tag on a misleveled embed-transcluded referenced heading is also a violation."""
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


class TestAllCoverImageValuesLegal:
    """all_cover_image_values_legal() requires a block ref resolving to an image vertex in the tree."""

    def test_resolvable_image_ref_passes(self) -> None:
        """A block ref to an in-tree ImageVertex produces no error."""
        assert all_cover_image_values_legal(_covered_tree()) is None

    def test_non_block_ref_value_is_reported(self) -> None:
        """A value that is not a block reference is a violation."""
        error = all_cover_image_values_legal(_covered_tree(value="![](https://example.com/c.jpg)"))
        assert error is not None
        assert "illegal cover-image values" in error.message
        assert "block reference" in error.message

    def test_unresolvable_target_is_reported(self) -> None:
        """A reference to a UID absent from the tree is a violation."""
        error = all_cover_image_values_legal(_covered_tree(with_image=False))
        assert error is not None
        assert "absent from the tree" in error.message

    def test_non_image_target_is_reported(self) -> None:
        """A reference to a non-image vertex is a violation."""
        page = PageVertex(
            uid="pageroot1", title="Doc", attribute_assignments=[_assignment("cover-image", "((textblok1))")]
        )
        tree = VertexTree(tree_vertices=[page], ref_vertices=[TextVertex(uid="textblok1", text="not an image")])
        error = all_cover_image_values_legal(tree)
        assert error is not None
        assert "not an image" in error.message

    def test_cover_image_on_heading_is_misanchored(self) -> None:
        """A cover-image attribute on a non-root heading is reported by the anchor validator."""
        tree = _attributed_tree([], ["cover-image"], AttributeDomain.GUFFIN, value="((imgcover1))")
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "cover-image" in error.message


class TestAllDateValuesLegal:
    """all_date_values_legal() requires every date value to be a W3CDTF reduced-precision date."""

    def test_legal_value_passes(self) -> None:
        """A year-only date produces no error."""
        tree = _attributed_tree(["date"], [], AttributeDomain.GUFFIN, value="1298")
        assert all_date_values_legal(tree) is None

    def test_illegal_value_is_reported(self) -> None:
        """A prose date is a violation."""
        tree = _attributed_tree(["date"], [], AttributeDomain.GUFFIN, value="July 10, 1298")
        error = all_date_values_legal(tree)
        assert error is not None
        assert "illegal date values" in error.message
        assert "uid='pageroot1'" in error.message

    def test_surfaces_through_validate_semantics(self) -> None:
        """An illegal date value fails validate_semantics."""
        result = validate_semantics(_attributed_tree(["date"], [], AttributeDomain.GUFFIN, value="July 10, 1298"))
        assert not result.is_valid
        assert any("illegal date values" in error.message for error in result.errors)


class TestAllElementNumbersWellFormed:
    """all_element_numbers_well_formed flags number-shaped heading leads that do not parse."""

    def test_well_formed_numbers_pass(self) -> None:
        """Dotted, unpadded markers are well-formed."""
        tree = _flat_headed_tree(("head0000a", "[0.1] Acknowledgments"), ("head0000b", "[1.1] Book I"))
        assert all_element_numbers_well_formed(tree) is None

    def test_unnumbered_heading_passes(self) -> None:
        """A heading with no marker is ordinary text, not an attempt."""
        tree = _flat_headed_tree(("head0000a", "A.D. 1290."))
        assert all_element_numbers_well_formed(tree) is None

    def test_bare_single_segment_fails(self) -> None:
        """A bare bracketed integer on a heading is a malformed element number."""
        tree = _flat_headed_tree(("head0000a", "[1] Book I"))
        error = all_element_numbers_well_formed(tree)
        assert error is not None
        assert "head0000a" in error.message

    def test_padded_segment_fails(self) -> None:
        """A padded segment on a heading is a malformed element number."""
        tree = _flat_headed_tree(("head0000a", "[01.2] Chapter"))
        error = all_element_numbers_well_formed(tree)
        assert error is not None
        assert "head0000a" in error.message


class TestAllElementNumbersInHeadingsOnly:
    """all_element_numbers_in_headings_only flags dotted markers leading non-heading text."""

    def test_dotted_marker_on_text_vertex_fails(self) -> None:
        """A dotted number-shaped lead on a plain text block is a violation."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["text0000a"])
        stray = TextVertex(uid="text0000a", text="[1.2] should have been a heading")
        error = all_element_numbers_in_headings_only(VertexTree(tree_vertices=[page, stray]))
        assert error is not None
        assert "text0000a" in error.message

    def test_footnote_label_on_text_vertex_passes(self) -> None:
        """A bare bracketed integer in prose is a footnote/citation label, not an element number."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["text0000a"])
        footnote = TextVertex(uid="text0000a", text="[1] See Letter of Fr. Odoric.")
        assert all_element_numbers_in_headings_only(VertexTree(tree_vertices=[page, footnote])) is None

    def test_numbered_heading_passes(self) -> None:
        """A numbered heading is the legal host."""
        tree = _flat_headed_tree(("head0000a", "[1.1] Book I"))
        assert all_element_numbers_in_headings_only(tree) is None


class TestAllElementNumberMattersLegal:
    """all_element_number_matters_legal flags leading segments outside the matter convention."""

    def test_conventional_segments_pass(self) -> None:
        """Leading 0, 1, and 2 name the three matter divisions."""
        tree = _flat_headed_tree(
            ("head0000a", "[0.1] Preface"), ("head0000b", "[1.1] Body"), ("head0000c", "[2.1] Appendix")
        )
        assert all_element_number_matters_legal(tree) is None

    def test_leading_three_fails(self) -> None:
        """A leading segment outside 0-2 has no matter."""
        tree = _flat_headed_tree(("head0000a", "[3.1] Nowhere"))
        error = all_element_number_matters_legal(tree)
        assert error is not None
        assert "head0000a" in error.message


class TestAllElementNumberMattersAgree:
    """all_element_number_matters_agree flags number-vs-tag matter disagreement."""

    def test_agreeing_number_and_tag_pass(self) -> None:
        """A body-matter number on an element-type chapter (body matter) agrees."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["head0000a"])
        heading = HeadingVertex(
            uid="head0000a",
            text="[1.1] Chapter One",
            heading_level=1,
            attribute_assignments=[_assignment("element-type", "chapter")],
        )
        assert all_element_number_matters_agree(VertexTree(tree_vertices=[page, heading])) is None

    def test_untagged_numbered_heading_passes(self) -> None:
        """With no tags there is nothing to disagree with."""
        tree = _flat_headed_tree(("head0000a", "[0.1] Preface"))
        assert all_element_number_matters_agree(tree) is None

    def test_disagreeing_number_and_tag_fail(self) -> None:
        """A front-matter number on an element-type chapter (body matter) is a violation."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["head0000a"])
        heading = HeadingVertex(
            uid="head0000a",
            text="[0.1] Chapter One",
            heading_level=1,
            attribute_assignments=[_assignment("element-type", "chapter")],
        )
        error = all_element_number_matters_agree(VertexTree(tree_vertices=[page, heading]))
        assert error is not None
        assert "head0000a" in error.message
        assert "front-matter" in error.message
        assert "body-matter" in error.message


class TestAllElementNumbersUnique:
    """all_element_numbers_unique flags a number appearing on more than one heading."""

    def test_distinct_numbers_pass(self) -> None:
        """Distinct numbers are unique."""
        tree = _flat_headed_tree(("head0000a", "[1.1] One"), ("head0000b", "[1.2] Two"))
        assert all_element_numbers_unique(tree) is None

    def test_duplicate_numbers_fail(self) -> None:
        """The same number on two headings is a violation naming both."""
        tree = _flat_headed_tree(("head0000a", "[1.1] One"), ("head0000b", "[1.1] Other One"))
        error = all_element_numbers_unique(tree)
        assert error is not None
        assert "head0000a" in error.message
        assert "head0000b" in error.message


class TestAllElementNumbersOrdered:
    """all_element_numbers_ordered flags document order that breaks number order."""

    def test_increasing_order_passes(self) -> None:
        """Numbers rendering in increasing order pass."""
        tree = _flat_headed_tree(("head0000a", "[0.1] Preface"), ("head0000b", "[1.1] Body"))
        assert all_element_numbers_ordered(tree) is None

    def test_unnumbered_heading_does_not_participate(self) -> None:
        """An unnumbered heading between numbered ones does not break the chain."""
        tree = _flat_headed_tree(("head0000a", "[1.1] One"), ("head0000b", "A.D. 1290."), ("head0000c", "[1.2] Two"))
        assert all_element_numbers_ordered(tree) is None

    def test_decreasing_order_fails(self) -> None:
        """A lower number rendering after a higher one is placement drift."""
        tree = _flat_headed_tree(("head0000a", "[1.2] Two"), ("head0000b", "[1.1] One"))
        error = all_element_numbers_ordered(tree)
        assert error is not None
        assert "head0000b" in error.message
        assert "head0000a" in error.message


class TestAllElementNumbersNested:
    """all_element_numbers_nested flags nesting that breaks element-number prefixes."""

    def test_prefix_nesting_passes(self) -> None:
        """A chapter number extending its part's number nests legally."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["parthead1"])
        part = HeadingVertex(uid="parthead1", text="[1.1] Part One", heading_level=1, children=["chaphead1"])
        chapter = HeadingVertex(uid="chaphead1", text="[1.1.1] Chapter One", heading_level=2)
        assert all_element_numbers_nested(VertexTree(tree_vertices=[page, part, chapter])) is None

    def test_foreign_number_nested_fails(self) -> None:
        """A number nested under a numbered ancestor that is not its prefix is a violation."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["parthead1"])
        part = HeadingVertex(uid="parthead1", text="[1.1] Part One", heading_level=1, children=["chaphead1"])
        chapter = HeadingVertex(uid="chaphead1", text="[1.2.1] Foreign Chapter", heading_level=2)
        error = all_element_numbers_nested(VertexTree(tree_vertices=[page, part, chapter]))
        assert error is not None
        assert "chaphead1" in error.message

    def test_sibling_numbers_are_unconstrained(self) -> None:
        """Numbered siblings have no numbered ancestor and are not nesting-constrained."""
        tree = _flat_headed_tree(("head0000a", "[1.1] One"), ("head0000b", "[1.2] Two"))
        assert all_element_numbers_nested(tree) is None

    def test_ancestor_context_threads_through_embed(self) -> None:
        """A transcluded heading nests under the embed site's numbered ancestor."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["parthead1"])
        part = HeadingVertex(uid="parthead1", text="[1.1] Part One", heading_level=1, children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="chaphead1"))
        foreign = HeadingVertex(uid="chaphead1", text="[1.2.5] Transcluded Foreign", heading_level=2)
        tree = VertexTree(tree_vertices=[page, part, embed], ref_vertices=[foreign])
        error = all_element_numbers_nested(tree)
        assert error is not None
        assert "chaphead1" in error.message
