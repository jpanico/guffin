"""Tests for guffin.model.publishing_semantics."""

import logging

import pytest
import yaml
from conftest import FIXTURES_YAML_DIR
from pydantic import HttpUrl, ValidationError

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
from guffin.model.chicago_structure import Matter, StructuralElement
from guffin.model.code_source import CodeSource
from guffin.model.publishing_semantics import (
    DEFAULT_PDF_RENDER,
    DEFAULT_PUBLISH,
    PdfRender,
    PublishingAttribute,
    PublishingSemantics,
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
    code_language_of,
    code_language_of_vertex,
    code_source_of,
    code_source_of_vertex,
    cover_image_of,
    cover_image_vertex,
    date_of,
    drop_unpublished,
    element_type_of,
    element_type_of_vertex,
    find_publishing_attribute,
    has_element_type,
    has_parts,
    illustrators_of_vertex,
    matter_of,
    matter_of_vertex,
    pdf_render_of,
    pdf_render_of_vertex,
    promote_non_body_sections,
    publish_of,
    publish_of_vertex,
    resolved_matter,
    revision_of,
    revision_of_vertex,
    strip_element_numbers,
    validate_semantics,
)
from guffin.model.vertex import (
    BlockEmbedVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageEmbedVertex,
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
        assert root_members == {
            "title",
            "subtitle",
            "authors",
            "illustrators",
            "date",
            "publisher",
            "rights",
            "identifier",
            "language",
            "description",
            "revision",
            "cover-image",
        }

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


def _article7_vertex_tree() -> VertexTree:
    """Load the [[Test Article]] 7 VertexTree from its YAML fixture."""
    raw = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_7_vertices.yaml").read_text())
    return VertexTree(tree_vertices=[vertex_adapter.validate_python(r) for r in raw])


class TestElementTypeOfArticle7Fixture:
    """element_type_of resolves the real element-type tags in the [[Test Article]] 7 fixture."""

    def test_resolves_all_tagged_headings(self) -> None:
        """Every element-type-tagged heading resolves to the StructuralElement its tag names."""
        tree = _article7_vertex_tree()
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
            "XEToYEzri": StructuralElement.CHAPTER,
            "4GZFNJcwy": StructuralElement.CHAPTER,
            "z26IaDo-5": StructuralElement.CHAPTER,
            "FwvqbfWO6": StructuralElement.CHAPTER,
            "_v0DthR5H": StructuralElement.CHAPTER,
            "QUB_je_gL": StructuralElement.CHAPTER,
            "YKIfOxGfE": StructuralElement.CHAPTER,
            "ff4xkJQQl": StructuralElement.CHAPTER,
            "LZ2nMx2H0": StructuralElement.CHAPTER,
            "L0xspxsKt": StructuralElement.CHAPTER,
            "kwMdW-Srm": StructuralElement.CHAPTER,
            "6XANyGEAN": StructuralElement.CHAPTER,
            "3g17AnfDf": StructuralElement.CHAPTER,
            "lZKsMSgZX": StructuralElement.PART,
            "6yQMbdz2s": StructuralElement.CHAPTER,
            "X30XeVcFj": StructuralElement.CHAPTER,
            "IpvhvPgDJ": StructuralElement.CHAPTER,
            "QTm37UX2K": StructuralElement.CHAPTER,
            "3gplE69LF": StructuralElement.CHAPTER,
            "wuedDMpZ3": StructuralElement.CHAPTER,
            "gXVxIg-yg": StructuralElement.CHAPTER,
            "wps9VKUCW": StructuralElement.CHAPTER,
            "qONAkcn_A": StructuralElement.CHAPTER,
            "fnF6lC-Q-": StructuralElement.CHAPTER,
            "hiJOL_Qz5": StructuralElement.SECTION,
            "yoDIZS8Cq": StructuralElement.CHAPTER,
            "2GuxTiNnf": StructuralElement.CHAPTER,
            "zXhYsKp5A": StructuralElement.CHAPTER,
            "09KMheZHg": StructuralElement.PART,
            "MGvH7SY4M": StructuralElement.PART,
        }

    def test_acknowledgments_heading_resolves(self) -> None:
        """The Acknowledgements heading's element-type tag resolves to ACKNOWLEDGMENTS via find + coerce."""
        heading = next(v for v in VertexTreeDFSIterator(_article7_vertex_tree()) if v.uid == "dpoX6c0Pl")
        assignment = find_publishing_attribute(heading, PublishingSemantics.ELEMENT_TYPE)
        assert assignment is not None
        assert element_type_of(assignment) is StructuralElement.ACKNOWLEDGMENTS


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


def _code_block_with(assignments: list[AttributeAssignment] | None) -> CodeBlockVertex:
    """A python code-block vertex carrying *assignments*."""
    return CodeBlockVertex(uid="codeuid01", code="print(1)", language="python", attribute_assignments=assignments)


class TestCodeLanguageOf:
    """code_language_of validates the attribute identity and resolves the value to a canonical id."""

    def test_returns_canonical_id(self) -> None:
        """A valid code-language assignment yields the canonical language id."""
        assert code_language_of(_assignment("code-language", "FORTRAN")) == "fortran"

    def test_alias_resolves(self) -> None:
        """A vocabulary alias resolves to the canonical id."""
        assert code_language_of(_assignment("code-language", "gnu asm")) == "unix assembly"

    def test_wrong_attribute_name_rejected(self) -> None:
        """An assignment for a different attribute raises, even with a valid language value."""
        with pytest.raises(ValueError):
            code_language_of(_assignment("matter", "fortran"))

    def test_unknown_language_rejected(self) -> None:
        """A value outside the canonical vocabulary raises."""
        with pytest.raises(ValueError):
            code_language_of(_assignment("code-language", "edsac"))


class TestCodeLanguageOfVertex:
    """code_language_of_vertex() resolves a code block's code-language tag, tolerating absence and junk."""

    def test_tagged_code_block_resolves(self) -> None:
        """A code-language tag resolves to its canonical id."""
        vertex = _code_block_with([_assignment("code-language", "Fortran")])
        assert code_language_of_vertex(vertex) == "fortran"

    def test_untagged_is_none(self) -> None:
        """An untagged code block resolves to None (the fence language stands)."""
        assert code_language_of_vertex(_code_block_with(None)) is None

    def test_illegal_value_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A junk code-language value is ignored (warned), not raised."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert code_language_of_vertex(_code_block_with([_assignment("code-language", "edsac")])) is None
        assert "ignoring code-language" in caplog.text


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


_SOURCE_URL = "https://raw.githubusercontent.com/psf/requests/main/src/requests/api.py#L14-L60"
_SOURCE_SHA = "0d9ca427f7d7dbe92694284d4a6249178255036e"
_SOURCE_DATE = "2026-07-17"


def _code_source_assignment(
    url: str = _SOURCE_URL, sha: str = _SOURCE_SHA, date: str = _SOURCE_DATE
) -> AttributeAssignment:
    """Build a three-valued code-source assignment (url, commit sha, fetched date)."""
    return _multi_assignment("code-source", url, sha, date)


class TestCodeSourceOf:
    """code_source_of validates the attribute identity, the arity, and each of the three values."""

    def test_returns_code_source(self) -> None:
        """A legal three-valued assignment yields the parsed CodeSource."""
        source = code_source_of(_code_source_assignment())
        assert source == CodeSource(url=_SOURCE_URL, commit_sha=_SOURCE_SHA, fetched_date=_SOURCE_DATE)

    def test_wrong_attribute_name_rejected(self) -> None:
        """An assignment for a different attribute raises, even with legal values."""
        with pytest.raises(ValueError):
            code_source_of(_multi_assignment("code-language", _SOURCE_URL, _SOURCE_SHA, _SOURCE_DATE))

    @pytest.mark.parametrize("count", [1, 2, 4])
    def test_wrong_arity_rejected(self, count: int) -> None:
        """An assignment with other than three values raises."""
        with pytest.raises(ValueError, match="3 values"):
            code_source_of(_multi_assignment("code-source", *([_SOURCE_URL, _SOURCE_SHA, _SOURCE_DATE] * 2)[:count]))

    def test_unparseable_url_rejected(self) -> None:
        """A first value that is not a raw GitHub URL raises."""
        with pytest.raises(ValueError, match="raw.githubusercontent.com"):
            code_source_of(_code_source_assignment(url="https://example.com/f.py"))

    def test_abbreviated_sha_rejected(self) -> None:
        """A second value that is not a full 40-hex SHA raises."""
        with pytest.raises(ValueError, match="40-hex"):
            code_source_of(_code_source_assignment(sha="0d9ca42"))

    def test_reduced_precision_date_rejected(self) -> None:
        """A third value not at full YYYY-MM-DD precision raises."""
        with pytest.raises(ValueError, match="valid date"):
            code_source_of(_code_source_assignment(date="2026-07"))


class TestCodeSourceOfVertex:
    """code_source_of_vertex() resolves a code block's code-source tag, tolerating absence and junk."""

    def test_tagged_code_block_resolves(self) -> None:
        """A code-source tag resolves to its parsed CodeSource."""
        vertex = _code_block_with([_code_source_assignment()])
        source = code_source_of_vertex(vertex)
        assert source is not None
        assert source.commit_sha == _SOURCE_SHA

    def test_untagged_is_none(self) -> None:
        """An untagged code block resolves to None (no recorded provenance)."""
        assert code_source_of_vertex(_code_block_with(None)) is None

    def test_illegal_value_ignored_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A junk code-source value is ignored (warned), not raised."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert code_source_of_vertex(_code_block_with([_code_source_assignment(sha="junk")])) is None
        assert "ignoring code-source" in caplog.text


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


class TestPromoteNonBodySections:
    """promote_non_body_sections() lifts root-level explicit front/back-matter headings to level 1."""

    @staticmethod
    def _parts_tree(section_level: int, section_assignments: list[AttributeAssignment] | None) -> VertexTree:
        """A page with one part (level 1, with a level-2 chapter) and one trailing root-level section."""
        page = PageVertex(uid="page00001", title="Book", children=["part00001", "sect00001"])
        part = HeadingVertex(
            uid="part00001",
            text="Part I",
            heading_level=1,
            children=["chap00001"],
            attribute_assignments=[_assignment("element-type", "part")],
        )
        chapter = HeadingVertex(uid="chap00001", text="Chapter 1", heading_level=2)
        section = HeadingVertex(
            uid="sect00001",
            text="About the Author",
            heading_level=section_level,
            attribute_assignments=section_assignments,
        )
        return VertexTree(tree_vertices=[page, part, chapter, section])

    def test_back_matter_root_section_is_promoted(self) -> None:
        """A level-2 root child tagged back-matter lands at level 1."""
        tree = self._parts_tree(2, [_assignment("matter", "back-matter")])
        promoted = promote_non_body_sections(tree)
        section = promoted.uid_map["sect00001"]
        assert isinstance(section, HeadingVertex) and section.heading_level == 1

    def test_front_matter_element_type_is_promoted(self) -> None:
        """The conventional matter of an element-type tag qualifies too (no bare matter tag needed)."""
        tree = self._parts_tree(2, [_assignment("element-type", "preface")])
        promoted = promote_non_body_sections(tree)
        section = promoted.uid_map["sect00001"]
        assert isinstance(section, HeadingVertex) and section.heading_level == 1

    def test_untagged_root_section_is_left_alone(self) -> None:
        """A root child with no matter signal keeps its authored level."""
        tree = promote_non_body_sections(self._parts_tree(2, None))
        section = tree.uid_map["sect00001"]
        assert isinstance(section, HeadingVertex) and section.heading_level == 2

    def test_body_matter_root_section_is_left_alone(self) -> None:
        """An explicitly body-matter root child keeps its authored level."""
        tree = promote_non_body_sections(self._parts_tree(2, [_assignment("matter", "body-matter")]))
        section = tree.uid_map["sect00001"]
        assert isinstance(section, HeadingVertex) and section.heading_level == 2

    def test_level_1_section_needs_no_promotion(self) -> None:
        """A root child already at level 1 comes back unchanged (the whole tree untouched)."""
        tree = self._parts_tree(1, [_assignment("matter", "back-matter")])
        assert promote_non_body_sections(tree) == tree

    def test_non_body_section_nested_inside_a_part_is_left_alone(self) -> None:
        """Hierarchy wins: a back-matter-tagged heading inside a part is not a root section."""
        page = PageVertex(uid="page00001", title="Book", children=["part00001"])
        part = HeadingVertex(
            uid="part00001",
            text="Part I",
            heading_level=1,
            children=["nest00001"],
            attribute_assignments=[_assignment("element-type", "part")],
        )
        nested = HeadingVertex(
            uid="nest00001",
            text="Appendix inside the part",
            heading_level=2,
            attribute_assignments=[_assignment("matter", "back-matter")],
        )
        tree = VertexTree(tree_vertices=[page, part, nested])
        promoted = promote_non_body_sections(tree)
        result = promoted.uid_map["nest00001"]
        assert isinstance(result, HeadingVertex) and result.heading_level == 2


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


class TestDateOf:
    """date_of() parses a date assignment's sole value into a W3CDTF reduced-precision date.

    Format-level cases live with the delegate (``tests/common/test_date.py``); these tests cover
    the vocabulary layer: attribute verification and the delegation itself.
    """

    def test_year_only(self) -> None:
        """A bare year (the CMOS-canonical publication date) is legal."""
        assert str(date_of(_assignment("date", "1298"))) == "1298"

    def test_full_date(self) -> None:
        """A full year-month-day date is legal."""
        assert str(date_of(_assignment("date", "1298-07-10"))) == "1298-07-10"

    def test_rejects_wrong_attribute(self) -> None:
        """An assignment for a different attribute is rejected."""
        with pytest.raises(ValueError, match="date"):
            date_of(_assignment("matter", "1298"))

    def test_rejects_non_w3cdtf_value(self) -> None:
        """A non-W3CDTF value is rejected (via the common verifier)."""
        with pytest.raises(ValueError, match="W3CDTF"):
            date_of(_assignment("date", "July 10, 1298"))


class TestCoverImageOf:
    """cover_image_of() reads a cover-image assignment's sole value as the referenced block's UID."""

    def test_block_ref_yields_uid(self) -> None:
        """A block reference ((uid)) yields the referenced UID."""
        assert cover_image_of(_assignment("cover-image", "((imgcover1))")) == "imgcover1"

    def test_rejects_wrong_attribute(self) -> None:
        """An assignment for a different attribute is rejected."""
        with pytest.raises(ValueError, match="cover-image"):
            cover_image_of(_assignment("matter", "((imgcover1))"))

    def test_rejects_bare_url(self) -> None:
        """A raw image URL is rejected — the value must be a block reference."""
        with pytest.raises(ValueError, match="block reference"):
            cover_image_of(_assignment("cover-image", "https://example.com/cover.jpeg"))

    def test_rejects_image_markdown(self) -> None:
        """CommonMark image syntax is rejected — the value must be a block reference."""
        with pytest.raises(ValueError, match="block reference"):
            cover_image_of(_assignment("cover-image", "![](https://example.com/cover.jpeg)"))

    def test_rejects_malformed_uid(self) -> None:
        """A block reference whose UID is not a legal Roam UID is rejected."""
        with pytest.raises(ValueError, match="block reference"):
            cover_image_of(_assignment("cover-image", "((not a uid))"))


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


class TestCoverImageVertex:
    """cover_image_vertex() follows the root's cover-image block ref to the ImageVertex it names."""

    def test_resolves_to_the_referenced_image(self) -> None:
        """The referenced ImageVertex is returned."""
        resolved = cover_image_vertex(_covered_tree())
        assert isinstance(resolved, ImageVertex)
        assert resolved.uid == "imgcover1"

    def test_unattributed_root_is_none(self) -> None:
        """A tree whose root carries no cover-image attribute resolves to None."""
        tree = VertexTree(tree_vertices=[PageVertex(uid="pageroot1", title="Doc")])
        assert cover_image_vertex(tree) is None

    def test_illegal_value_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A non-block-ref value is ignored with a warning."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert cover_image_vertex(_covered_tree(value="not a block ref")) is None
        assert any("ignoring cover-image" in record.message for record in caplog.records)

    def test_unresolvable_target_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A reference to a UID absent from the tree is ignored with a warning."""
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert cover_image_vertex(_covered_tree(with_image=False)) is None
        assert any("absent from the tree" in record.message for record in caplog.records)

    def test_non_image_target_is_none_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A reference to a non-image vertex is ignored with a warning."""
        page = PageVertex(
            uid="pageroot1", title="Doc", attribute_assignments=[_assignment("cover-image", "((textblok1))")]
        )
        tree = VertexTree(tree_vertices=[page], ref_vertices=[TextVertex(uid="textblok1", text="not an image")])
        with caplog.at_level(logging.WARNING, logger="guffin.model.publishing_semantics"):
            assert cover_image_vertex(tree) is None
        assert any("not an image" in record.message for record in caplog.records)


class TestRevisionOf:
    """revision_of() reads a revision assignment's sole free-text value verbatim."""

    def test_returns_the_label(self) -> None:
        """The sole value is returned unchanged."""
        assert revision_of(_assignment("revision", "draft-3")) == "draft-3"

    def test_rejects_wrong_attribute(self) -> None:
        """An assignment for a different attribute is rejected."""
        with pytest.raises(ValueError, match="revision"):
            revision_of(_assignment("title", "draft-3"))


class TestRevisionOfVertex:
    """revision_of_vertex() resolves a vertex's revision attribute, tolerating absence."""

    def test_attributed_vertex_resolves(self) -> None:
        """A page carrying the attribute resolves to its label."""
        page = PageVertex(uid="pageroot1", title="Doc", attribute_assignments=[_assignment("revision", "draft-3")])
        assert revision_of_vertex(page) == "draft-3"

    def test_unattributed_vertex_is_none(self) -> None:
        """A vertex with no revision attribute resolves to None."""
        assert revision_of_vertex(PageVertex(uid="pageroot1", title="Doc")) is None


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

    def test_page_embed_of_unpublished_target_vanishes(self) -> None:
        """A page embed whose transcluded page is unpublished is pruned with it."""
        root = PageVertex(uid="pageroot1", title="Doc", children=["keep00001", "embd00001"])
        embed = PageEmbedVertex(uid="embd00001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="refpage01"))
        target = PageVertex(uid="refpage01", title="Hidden", attribute_assignments=[_assignment("publish", "false")])
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


class TestIllustratorsOfVertex:
    """illustrators_of_vertex reads a vertex's declared illustrator names, tolerating absence."""

    def test_names_in_source_order(self) -> None:
        """Each value contributes its text, in source order."""
        assignment = AttributeAssignment(
            attribute=AttributeInstance(
                definition=Attribute(name="illustrators", domain=AttributeDomain.GUFFIN), link=_LINK
            ),
            values=(LiteralValue(value="Emi Panico"), LiteralValue(value="Ada Lovelace")),
        )
        vertex = PageVertex(uid="page00001", title="Doc", attribute_assignments=[assignment])
        assert illustrators_of_vertex(vertex) == ("Emi Panico", "Ada Lovelace")

    def test_absent_assignment_yields_empty(self) -> None:
        """A vertex with no illustrators assignment yields the empty tuple."""
        assert illustrators_of_vertex(PageVertex(uid="page00001", title="Doc")) == ()


def _flat_headed_tree(*headings: tuple[str, str]) -> VertexTree:
    """A page whose children are level-1 headings, given as (uid, text) pairs in document order."""
    page = PageVertex(uid="pageroot1", title="Doc", children=[uid for uid, _text in headings])
    vertices = [HeadingVertex(uid=uid, text=text, heading_level=1) for uid, text in headings]
    return VertexTree(tree_vertices=[page, *vertices])


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


class TestStripElementNumbers:
    """strip_element_numbers removes well-formed markers from headings and touches nothing else."""

    def test_numbered_heading_is_stripped(self) -> None:
        """A heading's well-formed marker is removed from its text."""
        tree = _flat_headed_tree(("head0000a", "[1.1] Book I"))
        stripped = strip_element_numbers(tree)
        heading = stripped.uid_map["head0000a"]
        assert isinstance(heading, HeadingVertex)
        assert heading.text == "Book I"

    def test_unnumbered_heading_is_unchanged(self) -> None:
        """A heading with no marker passes through unchanged."""
        tree = _flat_headed_tree(("head0000a", "A.D. 1290."))
        stripped = strip_element_numbers(tree)
        heading = stripped.uid_map["head0000a"]
        assert isinstance(heading, HeadingVertex)
        assert heading.text == "A.D. 1290."

    def test_malformed_lead_is_unchanged(self) -> None:
        """A malformed number-shaped lead is left in place (validation reports it instead)."""
        tree = _flat_headed_tree(("head0000a", "[1] Book I"))
        stripped = strip_element_numbers(tree)
        heading = stripped.uid_map["head0000a"]
        assert isinstance(heading, HeadingVertex)
        assert heading.text == "[1] Book I"

    def test_text_vertex_is_unchanged(self) -> None:
        """A text vertex keeps its bracketed lead — only headings carry element numbers."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["text0000a"])
        footnote = TextVertex(uid="text0000a", text="[1] See Letter of Fr. Odoric.")
        stripped = strip_element_numbers(VertexTree(tree_vertices=[page, footnote]))
        text = stripped.uid_map["text0000a"]
        assert isinstance(text, TextVertex)
        assert text.text == "[1] See Letter of Fr. Odoric."

    def test_referenced_heading_is_stripped(self) -> None:
        """A heading reachable only through ref_vertices (an embed target) is stripped too."""
        page = PageVertex(uid="pageroot1", title="Doc", children=["embed0001"])
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="chaphead1"))
        target = HeadingVertex(uid="chaphead1", text="[1.2.5] Transcluded Chapter", heading_level=2)
        stripped = strip_element_numbers(VertexTree(tree_vertices=[page, embed], ref_vertices=[target]))
        heading = stripped.uid_map["chaphead1"]
        assert isinstance(heading, HeadingVertex)
        assert heading.text == "Transcluded Chapter"

    def test_original_tree_is_not_modified(self) -> None:
        """The source tree keeps its markers; the transformer returns a new tree."""
        tree = _flat_headed_tree(("head0000a", "[1.1] Book I"))
        strip_element_numbers(tree)
        original = tree.uid_map["head0000a"]
        assert isinstance(original, HeadingVertex)
        assert original.text == "[1.1] Book I"
