"""Tests for guffin.cli.common."""

import logging
import textwrap
from unittest.mock import patch

import pytest
from conftest import article1_node_tree, asset_storage

from guffin.cli.common import (
    CodeSourceVerificationError,
    SemanticsValidationError,
    deduce_out_file_stem,
    fetch_roam_trees,
    resolve_profile,
)
from guffin.common.filenames import shell_safe_filename
from guffin.common.geometry import ImageSize
from guffin.common.media_type import MediaType
from guffin.common.table import Table, TableStyle
from guffin.common.validation import ValidationError, ValidationResult
from guffin.model.attribute import (
    Attribute,
    AttributeDomain,
    AttributeInstance,
    LiteralValue,
)
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source_diagnosis import CodeSourceDiagnosis, CodeSourceFinding
from guffin.model.publishing_semantics import PublishingSemantics
from guffin.model.vertex import (
    BlockEmbedVertex,
    CalloutVertex,
    CodeBlockVertex,
    HeadingVertex,
    ImageVertex,
    PageVertex,
    QuoteBlockVertex,
    TableVertex,
    TextVertex,
    Vertex,
)
from guffin.model.vertex_link import VertexLink, VertexLinkKind
from guffin.model.vertex_tree import VertexTree
from guffin.render.project import BookProfile, ProjectType, TopLevelDivision
from guffin.roam.code_language import CodeLanguage
from guffin.roam.local_api import ApiEndpoint
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec

_IMAGE_URL = (
    "https://firebasestorage.googleapis.com/v0/b/test.appspot.com" "/o/imgs%2Fphoto.jpeg?alt=media&token=abc123"
)


def _tree(root: Vertex) -> VertexTree:
    """Wrap a single root vertex in a VertexTree."""
    return VertexTree(tree_vertices=[root])


class TestDeduceOutFileStem:
    """Tests for deduce_out_file_stem()."""

    def test_page_uses_title(self) -> None:
        """A page root derives its stem from the page title."""
        tree = _tree(PageVertex(uid="page00001", title="My Page"))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "My_Page.article"

    def test_heading_uses_text(self) -> None:
        """A heading root derives its stem from the heading text."""
        tree = _tree(HeadingVertex(uid="headng001", text="Section One", heading_level=1))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "Section_One.article"

    def test_text_uses_text(self) -> None:
        """A text root derives its stem from the block text."""
        tree = _tree(TextVertex(uid="text00001", text="Some plain text"))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "Some_plain_text.article"

    def test_quote_block_uses_quote(self) -> None:
        """A quote-block root derives its stem from the quotation text."""
        tree = _tree(QuoteBlockVertex(uid="quote0001", quote="A quoted line"))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "A_quoted_line.article"

    def test_code_block_uses_code(self) -> None:
        """A code-block root derives its stem from the code content."""
        tree = _tree(CodeBlockVertex(uid="code00001", code="hello world", language=CodeLanguage.PYTHON))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "hello_world.article"

    def test_callout_prefers_title(self) -> None:
        """A callout root prefers its title when present."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="Important Note", body="some body"
        )
        assert deduce_out_file_stem(_tree(callout), ProjectType.ARTICLE) == "Important_Note.article"

    def test_callout_falls_back_to_body(self) -> None:
        """A callout root falls back to its body when the title is empty."""
        callout = CalloutVertex(
            uid="calout001", callout_type=CalloutVertex.CalloutType.INFO, title="", body="Fallback Body"
        )
        assert deduce_out_file_stem(_tree(callout), ProjectType.ARTICLE) == "Fallback_Body.article"

    def test_image_prefers_alt_text(self) -> None:
        """An image root prefers its alt text when present."""
        image = ImageVertex(
            uid="image0001",
            storage=asset_storage(_IMAGE_URL),
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
            alt_text="A flower",
        )
        assert deduce_out_file_stem(_tree(image), ProjectType.ARTICLE) == "A_flower.article"

    def test_image_falls_back_to_file_name(self) -> None:
        """An image root falls back to its source URL's filename when alt text is absent."""
        image = ImageVertex(
            uid="image0001",
            storage=asset_storage(_IMAGE_URL),
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        assert deduce_out_file_stem(_tree(image), ProjectType.ARTICLE) == "photo.jpeg.article"

    def test_image_falls_back_to_source(self) -> None:
        """An image root falls back to its source URL when it has no alt text and the URL encodes no filename."""
        # A short URL so textwrap.shorten leaves it intact (a long URL is one unbreakable
        # "word" and would collapse to the ellipsis placeholder).
        image = ImageVertex(
            uid="image0001",
            storage=asset_storage("http://example.com/"),
            media_type=MediaType.JPEG,
            scaled_image_size=ImageSize(),
        )
        assert (
            deduce_out_file_stem(_tree(image), ProjectType.ARTICLE)
            == shell_safe_filename(str(image.storage.location)) + ".article"
        )

    def test_table_joins_first_row_cells(self) -> None:
        """A table root joins the first row's cell values with underscores."""
        table = Table(rows=(("Name", "Age"), ("Bob", "30")))
        tree = _tree(TableVertex(uid="table0001", table=table, table_style=TableStyle()))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "Name_Age.article"

    def test_block_embed_recurses_into_target(self) -> None:
        """A block-embed root derives its stem from the embedded (referenced) vertex."""
        target = TextVertex(uid="target001", text="Embedded Target")
        embed = BlockEmbedVertex(uid="embed0001", vertex_link=VertexLink(kind=VertexLinkKind.EMBED, uid="target001"))
        tree = VertexTree(tree_vertices=[embed], ref_vertices=[target])
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "Embedded_Target.article"

    def test_appends_project_type(self) -> None:
        """The selected project type is appended as a ``.<type>`` segment before the extension."""
        tree = _tree(PageVertex(uid="page00001", title="My Page"))
        assert deduce_out_file_stem(tree, ProjectType.BOOK) == "My_Page.book"
        assert deduce_out_file_stem(tree, ProjectType.MANUSCRIPT) == "My_Page.manuscript"

    def test_long_basis_is_clipped(self) -> None:
        """A basis longer than 40 characters is shortened with a ``..._`` marker, then made shell-safe.

        The marker ends in ``_`` (retained by ``shell_safe_filename``, which strips only leading
        underscores) so that the appended ``.<type>`` segment reads ``..._.default`` rather than a
        run of dots ``....default``.
        """
        long_title = "This is a very long page title that certainly exceeds the limit"
        result = deduce_out_file_stem(_tree(PageVertex(uid="page00001", title=long_title)), ProjectType.ARTICLE)
        assert result == shell_safe_filename(textwrap.shorten(long_title, width=40, placeholder="..._")) + ".article"
        assert result.endswith("..._.article")

    def test_unwraps_markdown_links(self) -> None:
        """A rendered Markdown link in the basis is unwrapped to its text, dropping the URL."""
        # A page titled "[[Test Article]] 3" transcribes to a rendered page-ref link.
        tree = _tree(PageVertex(uid="page00001", title="[Test Article](x-guffin:vertex/LBFKibPIj) 3"))
        assert deduce_out_file_stem(tree, ProjectType.ARTICLE) == "Test_Article_3.article"

    def test_guffin_title_attribute_takes_precedence(self) -> None:
        """A guffin/title attribute on the root overrides the vertex's own title for the stem basis."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        page = PageVertex(
            uid="page00001",
            title="Page Title",
            attribute_assignments=[
                AttributeAssignment(
                    attribute=AttributeInstance(
                        definition=Attribute(name=PublishingSemantics.TITLE.value.name, domain=AttributeDomain.GUFFIN),
                        link=link,
                    ),
                    values=(LiteralValue(value="Override Title"),),
                )
            ],
        )
        assert deduce_out_file_stem(_tree(page), ProjectType.ARTICLE) == "Override_Title.article"

    def test_non_guffin_title_attribute_is_ignored(self) -> None:
        """A ``title`` attribute outside the guffin domain does not override the basis."""
        link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        page = PageVertex(
            uid="page00001",
            title="Page Title",
            attribute_assignments=[
                AttributeAssignment(
                    attribute=AttributeInstance(
                        definition=Attribute(name="title", domain=AttributeDomain.DEFAULT), link=link
                    ),
                    values=(LiteralValue(value="Override Title"),),
                )
            ],
        )
        assert deduce_out_file_stem(_tree(page), ProjectType.ARTICLE) == "Page_Title.article"


def _content_tree(part_tagged: bool) -> VertexTree:
    """A page with one level-1 heading, optionally tagged ``element-type:: part``."""
    link = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
    assignments = (
        [
            AttributeAssignment(
                attribute=AttributeInstance(
                    definition=Attribute(name="element-type", domain=AttributeDomain.GUFFIN), link=link
                ),
                values=(LiteralValue(value="part"),),
            )
        ]
        if part_tagged
        else None
    )
    page = PageVertex(uid="pageroot1", title="Doc", children=["head00001"])
    heading = HeadingVertex(uid="head00001", text="Book I", heading_level=1, attribute_assignments=assignments)
    return VertexTree(tree_vertices=[page, heading])


class TestResolveProfile:
    """resolve_profile() refines the project type's default profile from the content."""

    def test_book_with_part_tagged_content_becomes_parts_book(self) -> None:
        """A book whose content declares parts resolves to a with_parts BookProfile (PART division)."""
        profile = resolve_profile(ProjectType.BOOK, _content_tree(part_tagged=True))
        assert isinstance(profile, BookProfile)
        assert profile.with_parts is True
        assert profile.structural_policy.top_level_division is TopLevelDivision.PART

    def test_book_without_parts_keeps_chapter_division(self) -> None:
        """A book with no part-tagged headings keeps the default chapters-at-level-1 profile."""
        profile = resolve_profile(ProjectType.BOOK, _content_tree(part_tagged=False))
        assert isinstance(profile, BookProfile)
        assert profile.with_parts is False

    def test_non_book_type_ignores_part_tags(self) -> None:
        """Part-tagged content does not affect a non-book project type."""
        profile = resolve_profile(ProjectType.ARTICLE, _content_tree(part_tagged=True))
        assert not isinstance(profile, BookProfile)


def _dummy_validator(tree: VertexTree) -> ValidationError | None:
    """Stand-in validator identity for building synthetic ValidationResults."""
    return None


def _invalid_result() -> ValidationResult:
    """A ValidationResult carrying a single synthetic failure."""
    return ValidationResult(errors=(ValidationError(validator=_dummy_validator, message="synthetic violation"),))


class TestFetchRoamTreesStrictSemantics:
    """fetch_roam_trees() escalates vocabulary violations per its strict posture."""

    def _fetch(self, strict: bool) -> object:
        """Run fetch_roam_trees over the article1 fixture with validate_semantics forced invalid."""
        fetch_spec = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True)
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        endpoint = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="tok")
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.common.validate_semantics", return_value=_invalid_result()),
        ):
            return fetch_roam_trees(fetch_spec, True, endpoint, strict=strict)

    def test_strict_raises_on_violation(self) -> None:
        """strict=True turns a vocabulary violation into a SemanticsValidationError."""
        with pytest.raises(SemanticsValidationError) as exc_info:
            self._fetch(strict=True)
        assert "synthetic violation" in str(exc_info.value)
        assert not exc_info.value.result.is_valid

    def test_advisory_warns_and_succeeds(self, caplog: pytest.LogCaptureFixture) -> None:
        """strict=False (the default) logs the violation and returns the bundle."""
        with caplog.at_level(logging.WARNING, logger="guffin.cli.common"):
            result = self._fetch(strict=False)
        assert result is not None
        assert "synthetic violation" in caplog.text


def _drift_finding() -> CodeSourceFinding:
    """A synthetic drift finding for gate tests."""
    return CodeSourceFinding(
        uid="code00001",
        url="https://github.com/psf/requests/blob/main/setup.py",
        diagnosis=CodeSourceDiagnosis.DRIFT,
        detail="the source has moved on",
    )


class TestFetchRoamTreesCodeSourceGate:
    """fetch_roam_trees() runs the optional code-source gate at the caller's strict posture."""

    def _fetch(self, strict: bool, verify: bool, findings: tuple[CodeSourceFinding, ...]) -> object:
        """Run fetch_roam_trees over the article1 fixture with the verifier mocked to *findings*."""
        fetch_spec = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True)
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        endpoint = ApiEndpoint.from_parts(local_api_port=3333, graph_name="test", bearer_token="tok")
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch(
                "guffin.cli.code_source_verification.verify_code_sources", return_value=findings
            ) as self._mock_verify,
        ):
            return fetch_roam_trees(fetch_spec, True, endpoint, strict=strict, verify_code_sources=verify)

    def test_disabled_gate_never_calls_the_verifier(self) -> None:
        """verify_code_sources=False (the default) skips the network check entirely."""
        result = self._fetch(strict=True, verify=False, findings=(_drift_finding(),))
        assert result is not None
        self._mock_verify.assert_not_called()

    def test_strict_raises_on_findings(self) -> None:
        """The strict posture turns findings into a CodeSourceVerificationError."""
        with pytest.raises(CodeSourceVerificationError) as exc_info:
            self._fetch(strict=True, verify=True, findings=(_drift_finding(),))
        assert exc_info.value.findings[0].diagnosis is CodeSourceDiagnosis.DRIFT

    def test_advisory_warns_and_succeeds(self, caplog: pytest.LogCaptureFixture) -> None:
        """The advisory posture logs each finding as a warning and returns the bundle."""
        with caplog.at_level(logging.WARNING, logger="guffin.cli.common"):
            result = self._fetch(strict=False, verify=True, findings=(_drift_finding(),))
        assert result is not None
        assert "the source has moved on" in caplog.text

    def test_clean_verification_passes_silently(self) -> None:
        """No findings means no warnings and no raise, under either posture."""
        result = self._fetch(strict=True, verify=True, findings=())
        assert result is not None
        self._mock_verify.assert_called_once()
