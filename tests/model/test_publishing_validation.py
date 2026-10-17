"""Tests for guffin.model.publishing_validation."""

import yaml
from conftest import FIXTURES_YAML_DIR, YamlFixtureLoader, asset_storage
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
from guffin.model.notes import note_citations
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
    all_float_captions_present,
    all_float_contents_match,
    all_float_references_displayed,
    all_float_references_typed,
    all_float_values_legal,
    all_floats_displayed_once,
    all_matter_tags_at_section_level,
    all_matter_values_legal,
    all_note_form_values_legal,
    all_note_lead_ins_present,
    all_note_targets_in_notes_containers,
    all_note_targets_present,
    all_notes_cited_once,
    all_page_break_values_legal,
    all_pdf_render_values_legal,
    all_publish_values_legal,
    lead_ins_unique_within_sections,
    validate_semantics,
)
from guffin.model.vertex import (
    BlockEmbedVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    NotesVertex,
    PageVertex,
    PdfVertex,
    TextVertex,
    vertex_adapter,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
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
    raw = yaml.load((FIXTURES_YAML_DIR / "test_article_7_vertices.yaml").read_text(), Loader=YamlFixtureLoader)
    return VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])


def _article3_vertex_tree() -> VertexTree:
    """Load the [[Test Article]] 3 VertexTree from its YAML fixture, with its referenced PDF target.

    The fixture's external-links matrix standalone-references a PDF block living on
    [[Test Article]] 3's sibling article ``[[Test Article]] 1``, so that target vertex (from the
    article-1 fixture) rides along as a ref vertex — without it, the reference site's
    ``pdf-render`` tag could not resolve its standalone link target.
    """
    raw = yaml.load((FIXTURES_YAML_DIR / "test_article_3_vertices.yaml").read_text(), Loader=YamlFixtureLoader)
    article1_raw = yaml.load((FIXTURES_YAML_DIR / "test_article_1_vertices.yaml").read_text(), Loader=YamlFixtureLoader)
    pdf_target = next(vertex for vertex in article1_raw if vertex["uid"] == "pTvGGeTlB")
    return VertexTree(
        tree_vertices=[vertex_adapter.validate_python(r) for r in raw],
        ref_vertices=[vertex_adapter.validate_python(pdf_target)],
    )


def _heading_with(assignments: list[AttributeAssignment] | None) -> HeadingVertex:
    """A level-1 heading carrying *assignments*."""
    return HeadingVertex(uid="head00001", text="A Heading", heading_level=1, attribute_assignments=assignments)


_PDF_URL = "https://firebasestorage.googleapis.com/v0/b/test.appspot.com/o/pdfs%2Fa.pdf?alt=media&token=aaa"


def _pdf_with(assignments: list[AttributeAssignment] | None) -> PdfVertex:
    """A PDF vertex carrying *assignments*."""
    return PdfVertex(uid="pdfuid001", storage=asset_storage(_PDF_URL), attribute_assignments=assignments)


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
        storage=asset_storage(
            HttpUrl("https://firebasestorage.googleapis.com/v0/b/t/o/imgs%2Fcover.jpeg?alt=media&token=cov1")
        ),
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


class TestValidateSemanticsArticle3Fixture:
    """validate_semantics passes the [[Test Article]] 3 fixture, whose links matrix site-tags a PDF reference."""

    def test_fixture_is_semantically_valid(self) -> None:
        """The fixture's pdf-render tag at a standalone PDF reference site validates cleanly."""
        tree = _article3_vertex_tree()
        # Precondition: the fixture actually carries a pdf-render tag on a non-PDF (reference-site)
        # vertex, so a pass exercises the anchor's standalone-link transparency and is not vacuous.
        sites = [
            vertex
            for vertex in VertexTreeDFSIterator(tree)
            if not isinstance(vertex, PdfVertex)
            and find_publishing_attribute(vertex, PublishingSemantics.PDF_RENDER) is not None
        ]
        assert sites, "fixture carries no reference-site pdf-render tag; regenerate it from [[Test Article]] 3"
        result = validate_semantics(tree)
        assert result.errors == ()
        assert result.is_valid


class TestAllNoteFormValuesLegal:
    """all_note_form_values_legal() rejects unrecognised note-form values across a tree."""

    def test_legal_values_pass(self) -> None:
        """Both recognised forms validate, on any block."""
        page = PageVertex(uid="page00001", title="Doc", children=["text00001", "text00002"])
        short = TextVertex(uid="text00001", text="Short.", attribute_assignments=[_assignment("note-form", "short")])
        full = TextVertex(uid="text00002", text="Full.", attribute_assignments=[_assignment("note-form", "full")])
        tree = VertexTree(tree_vertices=[page, short, full])
        assert all_note_form_values_legal(tree) is None
        assert validate_semantics(tree).is_valid

    def test_illegal_value_reported(self) -> None:
        """An unrecognised note-form value is reported with the vertex uid."""
        page = PageVertex(uid="page00001", title="Doc", children=["text00001"])
        text = TextVertex(uid="text00001", text="Odd.", attribute_assignments=[_assignment("note-form", "medium")])
        error = all_note_form_values_legal(VertexTree(tree_vertices=[page, text]))
        assert error is not None
        assert "text00001" in error.message


class TestAllPageBreakValuesLegal:
    """all_page_break_values_legal() rejects unrecognised page-break values across a tree."""

    def test_legal_value_passes(self) -> None:
        """A tree whose page-break values are all recognised produces no error."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("page-break", "before")])])
        assert all_page_break_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """An unrecognised page-break value is reported with the vertex uid."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("page-break", "after")])])
        error = all_page_break_values_legal(tree)
        assert error is not None
        assert "head00001" in error.message

    def test_page_break_on_text_reported_by_anchor_validator(self) -> None:
        """A page-break tag on a text block is a misanchoring, caught by all_attributes_anchored."""
        text = TextVertex(
            uid="text00001", text="loose block", attribute_assignments=[_assignment("page-break", "before")]
        )
        tree = VertexTree(tree_vertices=[text])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "page-break" in error.message

    def test_surfaces_through_validate_semantics(self) -> None:
        """An illegal page-break value fails validate_semantics."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("page-break", "after")])])
        result = validate_semantics(tree)
        assert not result.is_valid
        assert any("page-break" in error.message for error in result.errors)


class TestAllPdfRenderValuesLegal:
    """all_pdf_render_values_legal() rejects unrecognised pdf-render values across a tree."""

    def test_legal_value_passes(self) -> None:
        """A tree whose pdf-render values are all recognised produces no error."""
        tree = VertexTree(tree_vertices=[_pdf_with([_assignment("pdf-render", "inline-native")])])
        assert all_pdf_render_values_legal(tree) is None

    def test_illegal_value_reported(self) -> None:
        """An unrecognised pdf-render value is reported with the vertex uid."""
        tree = VertexTree(tree_vertices=[_pdf_with([_assignment("pdf-render", "thumbnail")])])
        error = all_pdf_render_values_legal(tree)
        assert error is not None
        assert "pdfuid001" in error.message

    def test_pdf_render_on_heading_reported_by_anchor_validator(self) -> None:
        """A pdf-render tag on a heading is a misanchoring, caught by all_attributes_anchored."""
        tree = VertexTree(tree_vertices=[_heading_with([_assignment("pdf-render", "inline-native")])])
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

    def test_pdf_render_on_standalone_reference_to_pdf_passes(self) -> None:
        """A pdf-render tag at a standalone-link reference site whose target is a PDF is legal."""
        site = TextVertex(
            uid="refsite01",
            text="[a.pdf](x-guffin:vertex/pdfuid001)",
            attribute_assignments=[_assignment("pdf-render", "inline-native")],
        )
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, site], ref_vertices=[_pdf_with(None)])
        assert all_attributes_anchored(tree) is None

    def test_pdf_render_on_plain_text_vertex_is_reported(self) -> None:
        """A pdf-render tag on a text vertex that is no standalone PDF link stays a violation."""
        stray = TextVertex(
            uid="refsite01",
            text="just prose",
            attribute_assignments=[_assignment("pdf-render", "inline-native")],
        )
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, stray])
        error = all_attributes_anchored(tree)
        assert error is not None
        assert "'pdf-render' is pdf-anchored" in error.message

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


def _stray_text_tree(stray: TextVertex) -> VertexTree:
    """A page root whose sole child is *stray*."""
    page = PageVertex(uid="pageroot1", title="Doc", children=[stray.uid])
    return VertexTree(tree_vertices=[page, stray])


class TestAnchorMismatch:
    """_anchor_mismatch() checks every anchor axis: vertex type and tree position."""

    def test_root_anchored_on_root_vertex_passes(self) -> None:
        """A root-anchored attribute on the root vertex satisfies the anchor."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        root = PageVertex(uid="pageroot1", title="Doc")
        tree = VertexTree(tree_vertices=[root])
        assert _anchor_mismatch(attribute, root, "pageroot1", tree) is None

    def test_root_anchored_on_non_page_root_passes(self) -> None:
        """The root anchor is type-independent: a heading root (subtree export) also satisfies it."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        root = HeadingVertex(uid="head00001", text="H", heading_level=1)
        tree = VertexTree(tree_vertices=[root])
        assert _anchor_mismatch(attribute, root, "head00001", tree) is None

    def test_root_anchored_on_non_root_vertex_is_reported(self) -> None:
        """A root-anchored attribute anywhere but the root is a positional mismatch."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.ROOT)
        stray = TextVertex(uid="txt00001a", text="hello")
        mismatch = _anchor_mismatch(attribute, stray, "pageroot1", _stray_text_tree(stray))
        assert mismatch is not None
        assert "root-anchored" in mismatch
        assert "non-root vertex" in mismatch
        assert "uid='txt00001a'" in mismatch

    def test_type_mismatch_reported_before_position(self) -> None:
        """A vertex failing the type axis reports the type mismatch."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.HEADING)
        stray = TextVertex(uid="txt00001a", text="hello")
        mismatch = _anchor_mismatch(attribute, stray, "pageroot1", _stray_text_tree(stray))
        assert mismatch is not None
        assert "heading-anchored" in mismatch

    def test_link_transparent_anchor_satisfied_through_standalone_link(self) -> None:
        """A pdf-anchored attribute on a standalone-link host whose target is a PDF satisfies the anchor."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.PDF)
        site = TextVertex(uid="refsite01", text="[a.pdf](x-guffin:vertex/pdfuid001)")
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        tree = VertexTree(tree_vertices=[page, site], ref_vertices=[_pdf_with(None)])
        assert _anchor_mismatch(attribute, site, "pageroot1", tree) is None

    def test_link_transparent_anchor_rejects_non_matching_target(self) -> None:
        """A pdf-anchored attribute on a standalone link to a non-PDF target stays a type mismatch."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.PDF)
        site = TextVertex(uid="refsite01", text="[t](x-guffin:vertex/txttarget)")
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        target = TextVertex(uid="txttarget", text="plain")
        tree = VertexTree(tree_vertices=[page, site], ref_vertices=[target])
        mismatch = _anchor_mismatch(attribute, site, "pageroot1", tree)
        assert mismatch is not None
        assert "pdf-anchored" in mismatch

    def test_opaque_anchor_never_satisfied_through_link(self) -> None:
        """An anchor without link transparency (heading) rejects a standalone-link host regardless of target."""
        attribute = PublishingAttribute(name="test-attr", anchor=AttributeAnchor.HEADING)
        site = TextVertex(uid="refsite01", text="[h](x-guffin:vertex/refhead01)")
        page = PageVertex(uid="pageroot1", title="Doc", children=["refsite01"])
        target = HeadingVertex(uid="refhead01", text="H", heading_level=1)
        tree = VertexTree(tree_vertices=[page, site], ref_vertices=[target])
        mismatch = _anchor_mismatch(attribute, site, "pageroot1", tree)
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


def _note_link(lead_in: str, uid: str) -> str:
    """Return a Pandoc-Markdown note link with *lead_in* as its display, pointing at *uid*."""
    return f"[{lead_in}]({vertex_link_url(uid, VertexLinkKind.NOTE)})"


def _noted_page(*texts: str, notes: tuple[str, ...] = ("note00001",), extra: tuple[TextVertex, ...] = ()) -> VertexTree:
    """A page whose prose blocks are *texts*, with a notes container holding the notes *notes*."""
    prose_uids: list[str] = [f"text0000{index}" for index in range(1, len(texts) + 1)]
    page = PageVertex(uid="page00001", title="Doc", children=[*prose_uids, "notes0001"])
    prose = [TextVertex(uid=uid, text=text) for uid, text in zip(prose_uids, texts, strict=True)]
    container = NotesVertex(uid="notes0001", children=list(notes))
    note_vertices = [TextVertex(uid=uid, text=f"Note {uid}.") for uid in notes]
    return VertexTree(tree_vertices=[page, *prose, container, *note_vertices, *extra])


class TestAllNoteLeadInsPresent:
    """all_note_lead_ins_present rejects a note link whose display is blank or only a number."""

    def test_phrase_lead_in_passes(self) -> None:
        """A phrase is a lead-in."""
        assert all_note_lead_ins_present(_noted_page(_note_link("a 52-minute run", "note00001"))) is None

    def test_numbered_marker_fails(self) -> None:
        """A number left from a numbered marker carries no lead-in."""
        error = all_note_lead_ins_present(_noted_page(_note_link("1", "note00001")))
        assert error is not None
        assert "only a number ('1')" in error.message

    def test_blank_lead_in_fails(self) -> None:
        """A blank display carries no lead-in."""
        error = all_note_lead_ins_present(_noted_page(_note_link(" ", "note00001")))
        assert error is not None
        assert "no lead-in" in error.message


class TestAllNoteTargetsPresent:
    """all_note_targets_present rejects a note link whose note is absent."""

    def test_present_target_passes(self) -> None:
        """A link to a note in the tree passes."""
        assert all_note_targets_present(_noted_page(_note_link("lead", "note00001"))) is None

    def test_dangling_link_fails(self) -> None:
        """A link to a uid absent from the tree is dangling."""
        error = all_note_targets_present(_noted_page(_note_link("lead", "gone00001")))
        assert error is not None
        assert "gone00001" in error.message


class TestAllNotesCitedOnce:
    """all_notes_cited_once rejects a note cited by more than one note link."""

    def test_single_citation_passes(self) -> None:
        """A note cited once passes."""
        assert all_notes_cited_once(_noted_page(_note_link("lead", "note00001"))) is None

    def test_double_citation_fails(self) -> None:
        """A note cited from two passages is ambiguous."""
        error = all_notes_cited_once(_noted_page(_note_link("first", "note00001"), _note_link("second", "note00001")))
        assert error is not None
        assert "cited 2 times" in error.message


class TestAllNoteTargetsInNotesContainers:
    """all_note_targets_in_notes_containers rejects a note link to a block outside any notes container."""

    def test_contained_note_passes(self) -> None:
        """A link to a child of a notes container passes."""
        assert all_note_targets_in_notes_containers(_noted_page(_note_link("lead", "note00001"))) is None

    def test_ordinary_block_fails(self) -> None:
        """A link to an ordinary block would file it as a note."""
        tree = _noted_page(_note_link("lead", "loose0001"), extra=(TextVertex(uid="loose0001", text="Body."),))
        error = all_note_targets_in_notes_containers(tree)
        assert error is not None
        assert "loose0001" in error.message

    def test_dangling_link_is_left_to_targets_present(self) -> None:
        """A link to an absent uid is not reported here."""
        assert all_note_targets_in_notes_containers(_noted_page(_note_link("lead", "gone00001"))) is None


class TestLeadInsUniqueWithinSections:
    """lead_ins_unique_within_sections rejects two notes in one section sharing a lead-in."""

    @staticmethod
    def _chapter_tree(*, same_section: bool) -> VertexTree:
        """A chapter (level 1) with sections (level 2) whose prose cites two notes with one lead-in."""
        page = PageVertex(uid="page00001", title="Doc", children=["chap00001", "notes0001"])
        sections: list[str] = ["sect00001"] if same_section else ["sect00001", "sect00002"]
        chapter = HeadingVertex(uid="chap00001", text="Chapter", heading_level=1, children=sections)
        first_children: list[str] = ["texta0001", "textb0001"] if same_section else ["texta0001"]
        vertices = [
            page,
            chapter,
            HeadingVertex(uid="sect00001", text="A", heading_level=2, children=first_children),
            TextVertex(uid="texta0001", text=_note_link("the phrase", "note00001")),
            TextVertex(uid="textb0001", text=_note_link("the  phrase", "note00002")),
        ]
        if not same_section:
            vertices.append(HeadingVertex(uid="sect00002", text="B", heading_level=2, children=["textb0001"]))
        container = NotesVertex(uid="notes0001", children=["note00001", "note00002"])
        notes = [TextVertex(uid=uid, text="Note.") for uid in ("note00001", "note00002")]
        return VertexTree(tree_vertices=[*vertices, container, *notes])

    def test_same_lead_in_in_one_section_fails(self) -> None:
        """Two notes in one section with the same lead-in (whitespace aside) clash."""
        error = lead_ins_unique_within_sections(self._chapter_tree(same_section=True), section_level=2)
        assert error is not None
        assert "'the phrase'" in error.message
        assert "sect00001" in error.message

    def test_same_lead_in_in_different_sections_passes(self) -> None:
        """The same lead-in in two sections is keyed apart by the section."""
        assert lead_ins_unique_within_sections(self._chapter_tree(same_section=False), section_level=2) is None

    def test_coarser_section_level_merges_the_sections(self) -> None:
        """At section level 1 (an article), both sections fall under one heading and clash."""
        error = lead_ins_unique_within_sections(self._chapter_tree(same_section=False), section_level=1)
        assert error is not None
        assert "chap00001" in error.message


class TestValidateSemanticsNotes:
    """validate_semantics runs the note validators."""

    def test_numbered_marker_is_left_to_the_lead_in_check(self) -> None:
        """validate_semantics does not require lead-ins, which only invisible endnotes need."""
        tree = _noted_page(_note_link("1", "note00001"))
        assert validate_semantics(tree).is_valid
        assert all_note_lead_ins_present(tree) is not None

    def test_dangling_link_fails_by_default(self) -> None:
        """A note link whose note is absent fails the default validation."""
        assert not validate_semantics(_noted_page(_note_link("lead", "gone00001"))).is_valid

    def test_without_check_notes_the_note_validators_are_left_out(self) -> None:
        """With check_notes=False, as for notes that will not be rendered, a dangling note link passes."""
        assert validate_semantics(_noted_page(_note_link("lead", "gone00001")), check_notes=False).is_valid

    def test_without_check_notes_a_malformed_note_form_still_fails(self) -> None:
        """A malformed note-form value is a vocabulary error, not a note, so it is still reported."""
        page = PageVertex(uid="page00001", title="Doc", children=["text00001"])
        odd = TextVertex(uid="text00001", text="Odd.", attribute_assignments=[_assignment("note-form", "medium")])
        result = validate_semantics(VertexTree(tree_vertices=[page, odd]), check_notes=False)
        assert [error.validator for error in result.errors] == [all_note_form_values_legal]

    def test_article4_fixture_notes_validate(self) -> None:
        """[[Test Article]] 4's three Footnotes markers all carry phrase lead-ins, so the fixture validates."""
        raw = yaml.load((FIXTURES_YAML_DIR / "test_article_4_vertices.yaml").read_text(), Loader=YamlFixtureLoader)
        tree = VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])
        assert sorted(citation.lead_in for citation in note_citations(tree)) == [
            "ANCHOR NAME",
            "The anchor",
            "footnote anchor",
        ]
        result = validate_semantics(tree)
        assert result.errors == ()


_FIGURE_URL = "https://firebasestorage.googleapis.com/v0/b/t/o/imgs%2Fdiagram.png?alt=media&token=d1"


def _figure_image(uid: str = "imag00001") -> ImageVertex:
    """An image for a figure to wrap."""
    return ImageVertex(
        uid=uid, storage=asset_storage(_FIGURE_URL), media_type=MediaType.PNG, scaled_image_size=ImageSize()
    )


def _float_wrapper(uid: str, kind: str, caption: str, content_uid: str) -> TextVertex:
    """A float wrapper: a text block tagged ``float:: kind`` whose one child is *content_uid*."""
    return TextVertex(uid=uid, text=caption, children=[content_uid], attribute_assignments=[_assignment("float", kind)])


def _figure_tree(*extra: TextVertex, wrapper: TextVertex | None = None, displayed: bool = True) -> VertexTree:
    """A page holding a figure float (displayed, or kept among the refs) and *extra* text blocks."""
    the_wrapper = wrapper if wrapper is not None else _float_wrapper("wrap00001", "figure", "A diagram", "imag00001")
    children = ([the_wrapper.uid] if displayed else []) + [vertex.uid for vertex in extra]
    page = PageVertex(uid="page00001", title="Doc", children=children)
    tree_vertices: list[PageVertex | TextVertex | ImageVertex] = [page, *extra]
    refs: list[TextVertex | ImageVertex] = []
    (tree_vertices if displayed else refs).extend([the_wrapper, _figure_image()])
    return VertexTree(tree_vertices=tree_vertices, ref_vertices=refs)


def _link_to(display: str, uid: str) -> str:
    return f"[{display}]({vertex_link_url(uid, VertexLinkKind.REFERENCE)})"


class TestFloatValidators:
    """The float validators: a wrapper's tag, caption, and content, and the references to it."""

    def test_well_formed_figure_passes_every_rule(self) -> None:
        """A tagged, captioned wrapper over an image, displayed once and referenced by kind word, is clean."""
        tree = _figure_tree(TextVertex(uid="text00001", text=f"See {_link_to('figure', 'wrap00001')}."))
        for validator in (
            all_float_values_legal,
            all_float_captions_present,
            all_float_contents_match,
            all_float_references_typed,
            all_float_references_displayed,
            all_floats_displayed_once,
        ):
            assert validator(tree) is None, validator

    def test_illegal_kind_value(self) -> None:
        """A float value that is not a kind is reported."""
        tree = _figure_tree(wrapper=_float_wrapper("wrap00001", "diagram", "Cap", "imag00001"))
        error = all_float_values_legal(tree)
        assert error is not None
        assert "wrap00001" in error.message

    def test_blank_caption(self) -> None:
        """A wrapper whose text is blank has no caption."""
        tree = _figure_tree(wrapper=_float_wrapper("wrap00001", "figure", "  ", "imag00001"))
        error = all_float_captions_present(tree)
        assert error is not None
        assert "no caption" in error.message

    def test_content_of_the_wrong_kind(self) -> None:
        """A table tag over an image is a mismatch."""
        tree = _figure_tree(wrapper=_float_wrapper("wrap00001", "table", "Cap", "imag00001"))
        error = all_float_contents_match(tree)
        assert error is not None
        assert "wraps a guffin/image" in error.message

    def test_wrapper_without_a_single_child(self) -> None:
        """A wrapper with no child has no content."""
        wrapper = TextVertex(uid="wrap00001", text="Cap", attribute_assignments=[_assignment("float", "figure")])
        page = PageVertex(uid="page00001", title="Doc", children=["wrap00001"])
        error = all_float_contents_match(VertexTree(tree_vertices=[page, wrapper]))
        assert error is not None
        assert "exactly one child" in error.message

    def test_kind_word_naming_the_wrong_kind(self) -> None:
        """A table kind word on a figure wrapper is mistyped."""
        tree = _figure_tree(TextVertex(uid="text00001", text=f"See {_link_to('table', 'wrap00001')}."))
        error = all_float_references_typed(tree)
        assert error is not None
        assert "a figure" in error.message

    def test_kind_word_on_a_non_wrapper(self) -> None:
        """A kind word pointing at a bare image is mistyped: only a wrapper has a number."""
        tree = _figure_tree(TextVertex(uid="text00001", text=f"See {_link_to('figure', 'imag00001')}."))
        error = all_float_references_typed(tree)
        assert error is not None
        assert "not a float wrapper" in error.message

    def test_authors_own_alias_is_never_mistyped(self) -> None:
        """An alias that is not a kind word is the author's and passes."""
        tree = _figure_tree(TextVertex(uid="text00001", text=f"See {_link_to('the diagram', 'imag00001')}."))
        assert all_float_references_typed(tree) is None

    def test_reference_to_an_undisplayed_float(self) -> None:
        """A float kept among the refs and never displayed has no number for a reference to resolve to."""
        tree = _figure_tree(
            TextVertex(uid="text00001", text=f"See {_link_to('figure', 'wrap00001')}."), displayed=False
        )
        error = all_float_references_displayed(tree)
        assert error is not None
        assert "never displayed" in error.message

    def test_float_displayed_twice(self) -> None:
        """A second standalone reference to a wrapper displays it again."""
        showing = TextVertex(uid="show00001", text=_link_to("", "wrap00001"))
        tree = _figure_tree(showing)
        error = all_floats_displayed_once(tree)
        assert error is not None
        assert "displayed 2 times" in error.message

    def test_validate_semantics_runs_the_float_rules(self) -> None:
        """validate_semantics includes the float validators."""
        tree = _figure_tree(wrapper=_float_wrapper("wrap00001", "table", "Cap", "imag00001"))
        assert all_float_contents_match in [error.validator for error in validate_semantics(tree).errors]
