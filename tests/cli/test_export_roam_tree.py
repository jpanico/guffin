"""Unit tests for guffin.cli.export_roam_tree."""

import importlib.metadata
import logging
import os
import pathlib
import re
from typing import Final
from unittest.mock import MagicMock, patch

import pytest
import yaml
from conftest import (
    EPUB_SOURCE_DATE_EPOCH,
    FIXTURES_EPUB_DIR,
    FIXTURES_MD_DIR,
    FIXTURES_MDBUNDLE_DIR,
    FIXTURES_PDF_DIR,
    FIXTURES_YAML_DIR,
    PDF_CREATION_TIMESTAMP,
    YamlFixtureLoader,
    article1_node_tree,
)
from pypdf import PageObject, PdfReader
from typer.testing import CliRunner, Result

from guffin.cli.export_roam_tree import app
from guffin.common.provenance import Provenance
from guffin.common.validation import ValidationError, ValidationResult
from guffin.model.attribute import Attribute, AttributeDomain, AttributeInstance, LiteralValue
from guffin.model.attribute_assignment import AttributeAssignment
from guffin.model.code_source_diagnosis import CodeSourceDiagnosis, CodeSourceFinding
from guffin.model.publishing_semantics import NoteForm, PdfRenderPlacement
from guffin.model.render_bundle import RenderBundle
from guffin.model.vertex import HeadingVertex, NotesVertex, PageVertex, TextVertex, Vertex
from guffin.model.vertex_link import VertexLink, VertexLinkKind, vertex_link_url
from guffin.model.vertex_tree import VertexTree
from guffin.render.pandoc_rendering import heading_anchor
from guffin.render.project import BookProfile, NoteStyle, ProjectProfile, TopLevelDivision
from guffin.render.render_options import MarkdownRenderOptions
from guffin.roam.local_api import Response as LocalApiResponse
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec
from guffin.transcribe.roam_tree_to_guffin import transcribe


@pytest.mark.pandoc
class TestExportRoamTreeNoBundle:
    """Tests for export_roam_tree in --no-bundle mode."""

    def test_no_bundle_writes_expected_markdown(self, tmp_path: pathlib.Path) -> None:
        """Test that --no-bundle exports the correct GFM document.

        Loads nodes from the test_article_1_nodes.yaml fixture, mocks the Roam
        Local API fetch, invokes the CLI with --no-bundle, and asserts that the
        written .md file matches test_article_1_expected.md.
        """
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        runner: CliRunner = CliRunner()

        with patch(
            "guffin.cli.common.FetchRoamNodes.fetch_roam_nodes",
            return_value=mock_result,
        ):
            # configure_logging() runs at import time and installs a StreamHandler
            # on the root logger.  CliRunner closes its captured stream after invoke,
            # leaving a dangling handler that raises ValueError on the next write.
            # Temporarily clear root handlers to prevent that conflict.
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        output_file: pathlib.Path = tmp_path / "Test_Article_1.article.md"
        assert output_file.exists()
        expected: str = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert output_file.read_text() == expected


@pytest.mark.pandoc
class TestExportRoamTreeBundle:
    """Smoke tests for export_roam_tree in --bundle mode."""

    def test_bundle_exits_cleanly(self, tmp_path: pathlib.Path) -> None:
        """Bundle mode exits with code 0 and writes the expected .mdbundle directory and .md file."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        vertex_tree = transcribe(article1_node_tree())
        runner: CliRunner = CliRunner()

        with patch(
            "guffin.cli.common.FetchRoamNodes.fetch_roam_nodes",
            return_value=mock_result,
        ):
            with patch(
                "guffin.render.md_rendering.fetch_and_enrich_assets",
                return_value=(vertex_tree, {}),
            ):
                saved_handlers = logging.root.handlers[:]
                logging.root.handlers.clear()
                try:
                    result = runner.invoke(
                        app,
                        [
                            "[[Test Article]] 1",
                            "--port",
                            "3333",
                            "--graph",
                            "SCFH",
                            "--token",
                            "tok",
                            "--output-dir",
                            str(tmp_path),
                            "--bundle",
                        ],
                    )
                finally:
                    logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        bundle_dir: pathlib.Path = tmp_path / "Test_Article_1.article.mdbundle"
        assert bundle_dir.is_dir()
        assert (bundle_dir / "Test_Article_1.article.md").exists()


@pytest.mark.pandoc
class TestExportRoamTreeMdbundleFromRaw:
    """End-to-end test of export_roam_tree --bundle for [[Test Article]] 2, from the raw fetch result."""

    def test_mdbundle_from_raw_result_matches_fixture(self, tmp_path: pathlib.Path) -> None:
        """Exporting the bundle from the recorded raw Datalog response matches the baseline mdbundle.

        Drives the full pipeline offline: the only external boundary is stubbed.
        ``invoke_action`` (the Local API node fetch) returns the recorded
        ``test_article_2_raw_result.yaml`` wire response, so the real RoamNode parsing,
        tree build, transcription, and bundle rendering all run.  [[Test Article]] 2 has no
        Firebase Storage assets, so no asset fetch (hence no cache seeding) is needed — the
        empty ``--cache-dir`` keeps the run hermetic against a shell ``GUFFIN_CACHE_DIR``.
        """
        raw_result: Final[object] = yaml.load(
            (FIXTURES_YAML_DIR / "test_article_2_raw_result.yaml").read_text(), Loader=YamlFixtureLoader
        )
        api_response: Final[LocalApiResponse.Payload] = LocalApiResponse.Payload(success=True, result=raw_result)

        baseline: Final[pathlib.Path] = FIXTURES_MDBUNDLE_DIR / "Test_Article_2.article.mdbundle"
        cache_dir: Final[pathlib.Path] = tmp_path / "cache"
        cache_dir.mkdir()

        output_dir: Final[pathlib.Path] = tmp_path / "out"
        runner: CliRunner = CliRunner()
        with patch("guffin.roam.node_fetch.invoke_action", return_value=api_response):
            # configure_logging() installs a root StreamHandler at import time; CliRunner
            # closes its captured stream after invoke, leaving a dangling handler that
            # raises on the next write.  Clear root handlers for the duration of invoke.
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 2",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(output_dir),
                        "--format",
                        "markdown",
                        "--bundle",
                        "--cache-dir",
                        str(cache_dir),
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        actual: Final[pathlib.Path] = output_dir / "Test_Article_2.article.mdbundle"
        assert actual.is_dir()
        expected_names: Final[list[str]] = sorted(f.name for f in baseline.iterdir())
        actual_names: Final[list[str]] = sorted(f.name for f in actual.iterdir())
        assert actual_names == expected_names
        for name in expected_names:
            if name.endswith(".md"):
                assert (actual / name).read_text(encoding="utf-8") == (baseline / name).read_text(
                    encoding="utf-8"
                ), f"content mismatch: {name}"
            else:
                assert (actual / name).read_bytes() == (baseline / name).read_bytes(), f"content mismatch: {name}"


class TestExportRoamTreeNotFound:
    """Tests for export_roam_tree when the target page or node does not exist."""

    def _invoke(self, target: str, tmp_path: pathlib.Path) -> object:
        """Invoke the CLI with *target* and return the CliRunner result."""
        not_found_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier=target), include_refs=True
        )
        runner: CliRunner = CliRunner()
        with patch(
            "guffin.cli.common.FetchRoamNodes.fetch_roam_nodes",
            side_effect=RoamNodeNotFoundError(not_found_spec),
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                return runner.invoke(
                    app,
                    [target, "--port", "3333", "--graph", "SCFH", "--token", "tok", "--output-dir", str(tmp_path)],
                )
            finally:
                logging.root.handlers = saved_handlers

    def test_missing_page_exits_with_code_1(self, tmp_path: pathlib.Path) -> None:
        """A page title not present in Roam produces exit code 1."""
        result = self._invoke("DOES NOT EXIST", tmp_path)
        assert result.exit_code == 1  # type: ignore[union-attr]

    def test_missing_page_exits_cleanly_no_traceback(self, tmp_path: pathlib.Path) -> None:
        """Exit is a clean SystemExit, not an unhandled exception with a traceback."""
        result = self._invoke("DOES NOT EXIST", tmp_path)
        assert isinstance(result.exception, SystemExit)  # type: ignore[union-attr]

    def test_missing_page_writes_no_output_file(self, tmp_path: pathlib.Path) -> None:
        """No output file is written when the target page does not exist."""
        self._invoke("DOES NOT EXIST", tmp_path)
        assert list(tmp_path.iterdir()) == []


class TestExportRoamTreeMdbundleLive:
    """Live end-to-end test of export_roam_tree::main for the markdown bundle format."""

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_mdbundle_matches_fixture(self, tmp_path: pathlib.Path) -> None:
        """Exporting [[Test Article]] 3 as a markdown bundle matches the recorded baseline file-for-file.

        Roam credentials (GUFFIN_ROAM_*) are read from the environment by the CLI.
        """
        baseline: Final[pathlib.Path] = FIXTURES_MDBUNDLE_DIR / "Test_Article_3.article.mdbundle"
        assert baseline.exists(), (
            f"baseline mdbundle missing: {baseline}. Record it with: "
            'python tests/regen_fixtures.py "[[Test Article]] 3" --prefix test_article_3 --mdbundle'
        )
        runner: CliRunner = CliRunner()
        saved_handlers = logging.root.handlers[:]
        logging.root.handlers.clear()
        try:
            result = runner.invoke(
                app,
                ["[[Test Article]] 3", "--output-dir", str(tmp_path), "--format", "markdown", "--bundle"],
            )
        finally:
            logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        actual: Final[pathlib.Path] = tmp_path / "Test_Article_3.article.mdbundle"
        assert actual.exists()
        expected_names: Final[list[str]] = sorted(f.name for f in baseline.iterdir())
        actual_names: Final[list[str]] = sorted(f.name for f in actual.iterdir())
        assert actual_names == expected_names
        for name in expected_names:
            if name.endswith(".md"):
                assert (actual / name).read_text(encoding="utf-8") == (baseline / name).read_text(
                    encoding="utf-8"
                ), f"content mismatch: {name}"
            else:
                assert (actual / name).read_bytes() == (baseline / name).read_bytes(), f"content mismatch: {name}"


class TestExportRoamTreePdfLive:
    """Live end-to-end test of export_roam_tree::main for the PDF format."""

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_pdf_matches_fixture(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exporting [[Test Article]] 1 to PDF matches the recorded baseline byte-for-byte.

        Pins Typst's creation timestamp via GUFFIN_PDF_CREATION_TIMESTAMP so the output is
        reproducible; Roam credentials (GUFFIN_ROAM_*) are read from the environment by the CLI.
        """
        baseline: Final[pathlib.Path] = FIXTURES_PDF_DIR / "Test_Article_1.article.pdf"
        assert baseline.exists(), (
            f"baseline PDF missing: {baseline}. Record it with: "
            'python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1 --pdf'
        )
        monkeypatch.setenv("GUFFIN_PDF_CREATION_TIMESTAMP", str(PDF_CREATION_TIMESTAMP))
        runner: CliRunner = CliRunner()
        saved_handlers = logging.root.handlers[:]
        logging.root.handlers.clear()
        try:
            result = runner.invoke(
                app,
                ["[[Test Article]] 1", "--output-dir", str(tmp_path), "--format", "pdf"],
            )
        finally:
            logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        actual: Final[pathlib.Path] = tmp_path / "Test_Article_1.article.pdf"
        assert actual.exists()
        assert actual.read_bytes() == baseline.read_bytes()


class TestExportRoamTreeEpubLive:
    """Live end-to-end EPUB export against the recorded byte-reproducible baseline."""

    @pytest.mark.live
    @pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
    def test_live_epub_matches_fixture(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Exporting [[Test Article]] 6 as a book EPUB matches the recorded baseline byte-for-byte.

        Pins SOURCE_DATE_EPOCH so Pandoc's dcterms:modified and the package's zip entry
        timestamps are reproducible; Roam credentials (GUFFIN_ROAM_*) are read from the
        environment by the CLI.
        """
        baseline: Final[pathlib.Path] = FIXTURES_EPUB_DIR / "The_Picture_of_Dorian_Gray.book.epub"
        assert baseline.exists(), (
            f"baseline EPUB missing: {baseline}. Record it with: "
            'python tests/regen_fixtures.py "[[Test Article]] 6" --prefix test_article_6 --epub'
        )
        monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPUB_SOURCE_DATE_EPOCH))
        runner: CliRunner = CliRunner()
        saved_handlers = logging.root.handlers[:]
        logging.root.handlers.clear()
        try:
            result = runner.invoke(
                app,
                ["[[Test Article]] 6", "--output-dir", str(tmp_path), "--format", "epub", "--type", "book"],
            )
        finally:
            logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        actual: Final[pathlib.Path] = tmp_path / "The_Picture_of_Dorian_Gray.book.epub"
        assert actual.exists()
        assert actual.read_bytes() == baseline.read_bytes()


def _invoke_live_export(args: list[str]) -> Result:
    """Run export-roam-tree with *args*, detaching the root logging handlers for the invocation.

    configure_logging() installs a StreamHandler on the root logger at import time; CliRunner closes
    its captured stream after invoke, leaving a dangling handler that raises ValueError on the next
    write.
    """
    runner: Final[CliRunner] = CliRunner()
    saved_handlers = logging.root.handlers[:]
    logging.root.handlers.clear()
    try:
        return runner.invoke(app, args)
    finally:
        logging.root.handlers = saved_handlers


_TA3_INTERNAL_HEADING_UIDS: Final[tuple[str, ...]] = ("7XdTiY_ZF", "LfaVt18Iw", "ys3bY2GZa")
"""[[Test Article]] 3's in-page headings that its Internal (in-page) links section references.

``Feature Content``, ``Internal (in-page) links:``, and ``This header features a [[Test Article]] page
link`` — the last a heading whose text is itself a page link.
"""

_TA3_PAGE_LINK_HEADING_UID: Final[str] = "ys3bY2GZa"
"""The heading whose text is a page link, referenced inline by ``inline PAGE-LINK HEADER ref``."""


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
class TestExportRoamTreeCodeSourcesLive:
    """Live PDF export of [[Test Article]] 1 with ``--code-sources``: captions and attributions in order.

    Section 1.2 holds three listings — 1.2.1 with a caption child and no ``code-source::`` tag, 1.2.2
    with a tag and no caption, 1.2.3 with both — whose tags pin a commit SHA in the blob URL, so the
    export's default source verification fetches the immutable raw content and never drifts.  The
    baseline PDF (``TestExportRoamTreePdfLive``) is exported without code sources, so the attribution's
    rendering is pinned here, by the page text, rather than by bytes.
    """

    @pytest.fixture(scope="class")
    def page_text(self, tmp_path_factory: pytest.TempPathFactory) -> str:
        """The text of every page of [[Test Article]] 1 exported as an article PDF with code sources."""
        out_dir: Final[pathlib.Path] = tmp_path_factory.mktemp("ta1-code-sources-pdf")
        result: Final[Result] = _invoke_live_export(
            ["[[Test Article]] 1", "--output-dir", str(out_dir), "--format", "pdf", "--code-sources"]
        )
        assert result.exit_code == 0, result.output
        reader: Final[PdfReader] = PdfReader(out_dir / "Test_Article_1.article.pdf")
        return "\n".join(page.extract_text() for page in reader.pages)

    @staticmethod
    def _listing(page_text: str, number: str, next_heading: str) -> str:
        """The page text from the ``listing <number>`` heading up to *next_heading*."""
        start: Final[int] = page_text.index(f"listing {number}\n")
        return page_text[start : page_text.index(next_heading, start)]

    def test_captioned_listing_without_a_source_has_no_attribution(self, page_text: str) -> None:
        """Listing 1.2.1 sets its caption and no Source line."""
        listing: Final[str] = self._listing(page_text, "1.2.1", "listing 1.2.2")
        assert "A caption authored as the listing\u2019s child block." in listing
        assert "Source:" not in listing

    def test_sourced_listing_without_a_caption_sets_its_attribution(self, page_text: str) -> None:
        """Listing 1.2.2 sets its Source line, naming the file, and no caption."""
        listing: Final[str] = self._listing(page_text, "1.2.2", "listing 1.2.3")
        assert "Source: jpanico/guffin/src/guffin/common/json_value.py" in listing
        assert "A caption authored" not in listing

    def test_caption_precedes_attribution(self, page_text: str) -> None:
        """Listing 1.2.3 sets its caption, then its Source line with the line range."""
        listing: Final[str] = self._listing(page_text, "1.2.3", "Section 2\n")
        caption_at: Final[int] = listing.index("A caption authored as the listing\u2019s child block, set above")
        source_at: Final[int] = listing.index("Source: jpanico/guffin/src/guffin/common/geometry.py L1\u2013L8")
        assert caption_at < source_at


_TA1_HEADING_UID: Final[str] = "0EgPyHSZi"
"""Test Article 1's ``Section 1`` heading — referenced from Test Article 3 but outside its export."""


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
class TestExportRoamTreeHeadingLinksLive:
    """Live PDF export of [[Test Article]] 3: references to its headings become working internal links.

    Asserts the link structure itself rather than a byte baseline, so unrelated changes to the page's
    rendering do not disturb it.  One export suffices: fetching, transcribing, and resolving references
    against live uids is format-independent, and EPUB link routing is covered offline by
    ``tests/render/test_epub_rendering.py::TestHeadingLinkEpub``.
    """

    @pytest.fixture(scope="class")
    def pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """[[Test Article]] 3 exported as an article PDF."""
        out_dir: Final[pathlib.Path] = tmp_path_factory.mktemp("ta3-pdf")
        result: Final[Result] = _invoke_live_export(
            ["[[Test Article]] 3", "--output-dir", str(out_dir), "--format", "pdf"]
        )
        assert result.exit_code == 0, result.output
        return PdfReader(out_dir / "Test_Article_3.article.pdf")

    @staticmethod
    def _pdf_link_destinations(reader: PdfReader) -> list[str]:
        """Return the named destination of every link annotation in *reader*, in page order."""
        return [
            str(annot.get_object().get("/Dest"))
            for page in reader.pages
            for annot in page.get("/Annots") or []
            if annot.get_object().get("/Dest") is not None
        ]

    def test_pdf_links_each_internal_heading_reference(self, pdf: PdfReader) -> None:
        """Every referenced in-page heading is a named destination with a link pointing to it."""
        destinations: Final[list[str]] = self._pdf_link_destinations(pdf)
        for uid in _TA3_INTERNAL_HEADING_UIDS:
            assert heading_anchor(uid) in pdf.named_destinations, uid
            assert heading_anchor(uid) in destinations, uid

    def test_pdf_page_link_heading_destination_lands_on_the_heading(self, pdf: PdfReader) -> None:
        """The page-link heading's destination is the page that sets the heading."""
        destination = pdf.named_destinations[heading_anchor(_TA3_PAGE_LINK_HEADING_UID)]
        page_text: Final[str] = pdf.pages[pdf.get_destination_page_number(destination)].extract_text() or ""
        assert "This header features a Test Article page link" in page_text

    def test_pdf_out_of_export_heading_reference_is_not_linked(self, pdf: PdfReader) -> None:
        """A reference to a heading outside the export (Test Article 1) stays plain text."""
        assert heading_anchor(_TA1_HEADING_UID) not in pdf.named_destinations
        assert heading_anchor(_TA1_HEADING_UID) not in self._pdf_link_destinations(pdf)


_TA6_NOTE_LEAD_INS: Final[tuple[str, ...]] = (
    "creator of beautiful things",
    "the rage of Caliban",
    "the Grosvenor",
    "a Narcissus",
    "the face of Antinous",
)
"""The lead-ins of Test Article 6's five notes, in reading order: two in the Preface, three in chapter I."""


def _pdf_page_text(page: PageObject) -> str:
    """Return *page*'s text as one line of single-spaced words, rejoining words hyphenated at a line end."""
    return " ".join(re.sub(r"-\n", "", page.extract_text() or "").split())


@pytest.mark.live
@pytest.mark.skipif(not os.getenv("GUFFIN_LIVE_TESTS"), reason="requires Roam Desktop app running locally")
class TestExportRoamTreeNotesLive:
    """Live book PDF export of [[Test Article]] 6: its invisible endnotes, gathered and linked both ways.

    The five notes sit in ``#footnotes`` blocks on the embedded Preface and chapter I pages, and the
    Notes section opens at TA6's back-matter heading tagged ``element-type:: endnotes``.  Asserts the
    Notes page's content and the links rather than a byte baseline, so unrelated changes to the
    template do not disturb it.  The EPUB rendering of the same notes is pinned byte-for-byte by
    ``TestExportRoamTreeEpubLive``.
    """

    @staticmethod
    def _export(out_dir: pathlib.Path, *flags: str) -> PdfReader:
        """Export [[Test Article]] 6 as a book PDF into *out_dir*, with any extra CLI *flags*."""
        result: Final[Result] = _invoke_live_export(
            ["[[Test Article]] 6", "--output-dir", str(out_dir), "--format", "pdf", "--type", "book", *flags]
        )
        assert result.exit_code == 0, result.output
        return PdfReader(out_dir / "The_Picture_of_Dorian_Gray.book.pdf")

    @pytest.fixture(scope="class")
    def pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """[[Test Article]] 6 exported as a book PDF, its lead-ins underlined (the default)."""
        return self._export(tmp_path_factory.mktemp("ta6-pdf"))

    @pytest.fixture(scope="class")
    def print_pdf(self, tmp_path_factory: pytest.TempPathFactory) -> PdfReader:
        """[[Test Article]] 6 exported as a book PDF for print, with ``--no-note-ref-underline``."""
        return self._export(tmp_path_factory.mktemp("ta6-print-pdf"), "--no-note-ref-underline")

    @staticmethod
    def _notes_page(reader: PdfReader) -> int:
        """Return the index of the one page holding every note's entry."""
        pages: Final[list[int]] = [
            index
            for index, page in enumerate(reader.pages)
            if all(f"{lead_in}:" in _pdf_page_text(page) for lead_in in _TA6_NOTE_LEAD_INS)
        ]
        assert len(pages) == 1, pages
        return pages[0]

    @staticmethod
    def _passage_page(reader: PdfReader, lead_in: str) -> int:
        """Return the index of the one page outside the Notes whose running text holds *lead_in*."""
        notes_page: Final[int] = TestExportRoamTreeNotesLive._notes_page(reader)
        pages: Final[list[int]] = [
            index for index, page in enumerate(reader.pages) if index != notes_page and lead_in in _pdf_page_text(page)
        ]
        assert len(pages) == 1, (lead_in, pages)
        return pages[0]

    @staticmethod
    def _link_targets(reader: PdfReader, index: int) -> list[int]:
        """Return the index of the page each internal link on page *index* points to, in page order."""
        by_object: Final[dict[int, int]] = {
            page.indirect_reference.idnum: number
            for number, page in enumerate(reader.pages)
            if page.indirect_reference is not None
        }
        return [
            by_object[annot.get_object()["/Dest"][0].idnum]
            for annot in reader.pages[index].get("/Annots") or []
            if annot.get_object().get("/Dest") is not None
        ]

    @staticmethod
    def _dashed_strokes(page: PageObject) -> int:
        """Return how many dash patterns (``[…] phase d``, the array non-empty) *page*'s content sets.

        The dotted underline under a lead-in is the only dashed stroke on TA6's text pages.
        """
        contents: Final = page.get_contents()
        data: Final[bytes] = contents.get_data() if contents is not None else b""
        return len(re.findall(rb"\[[^\]]+\]\s*[\d.]+\s+d\b", data))

    def test_notes_page_groups_the_entries_by_chapter(self, pdf: PdfReader) -> None:
        """The Notes page groups the entries under Preface and I, each opening with a page number and its lead-in."""
        text: Final[str] = _pdf_page_text(pdf.pages[self._notes_page(pdf)])
        entries: Final[list[str]] = [rf"\d+ {re.escape(lead_in)}: .+" for lead_in in _TA6_NOTE_LEAD_INS]
        assert re.search(rf"Notes Preface {entries[0]} {entries[1]} I {' '.join(entries[2:])}", text), text

    def test_each_entry_gives_its_passage_page(self, pdf: PdfReader) -> None:
        """Each entry's locator is the displayed page number of the page that sets its passage."""
        text: Final[str] = _pdf_page_text(pdf.pages[self._notes_page(pdf)])
        for lead_in in _TA6_NOTE_LEAD_INS:
            # The page's displayed number is the last text on it, in the footer.
            displayed: str = _pdf_page_text(pdf.pages[self._passage_page(pdf, lead_in)]).split()[-1]
            assert f"{displayed} {lead_in}:" in text, lead_in

    def test_lead_ins_and_entries_link_to_each_other(self, pdf: PdfReader) -> None:
        """Every lead-in links to the Notes page, and every entry's locator links back to its passage page."""
        notes_page: Final[int] = self._notes_page(pdf)
        passage_pages: Final[list[int]] = [self._passage_page(pdf, lead_in) for lead_in in _TA6_NOTE_LEAD_INS]
        to_notes: Final[int] = sum(
            self._link_targets(pdf, page).count(notes_page) for page in sorted(set(passage_pages))
        )
        assert to_notes == len(_TA6_NOTE_LEAD_INS)
        assert self._link_targets(pdf, notes_page) == passage_pages

    def test_lead_ins_are_underlined_except_for_print(self, pdf: PdfReader, print_pdf: PdfReader) -> None:
        """A lead-in's page carries the dotted underline by default, and none for print, where it still links."""
        for lead_in in _TA6_NOTE_LEAD_INS:
            page: int = self._passage_page(pdf, lead_in)
            assert self._dashed_strokes(pdf.pages[page]) > 0, lead_in
            assert self._dashed_strokes(print_pdf.pages[page]) == 0, lead_in
            assert self._notes_page(print_pdf) in self._link_targets(print_pdf, page), lead_in


class TestExportRoamTreeStrictSemantics:
    """export-roam-tree aborts (exit 1) on guffin vocabulary violations; nothing is rendered."""

    def test_vocabulary_violation_aborts_export(self, tmp_path: pathlib.Path) -> None:
        """A validation failure in the fetched content exits with code 1 before any rendering."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        invalid: Final[ValidationResult] = ValidationResult(
            errors=(ValidationError(validator=lambda tree: None, message="synthetic violation"),)
        )
        runner: CliRunner = CliRunner()
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.common.validate_semantics", return_value=invalid),
            patch("guffin.cli.export_roam_tree.render_md") as mock_render_md,
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers
        assert result.exit_code == 1
        mock_render_md.assert_not_called()


class TestExportRoamTreeColophon:
    """The --colophon/--no-colophon flag controls whether the CLI gathers provenance for the renderer.

    The CLI's responsibility is to decide whether to capture provenance and hand it to the renderer
    on the render options; turning that provenance into a colophon in the output is the render layer's
    job and is covered there (``tests/render/test_pandoc_rendering.py``).  Mocking the renderer keeps
    these flag-plumbing checks fast — no Pandoc subprocess — while still exercising the full CLI path.
    """

    def _render_call_for_flag(
        self, tmp_path: pathlib.Path, colophon_flag: str
    ) -> tuple[RenderBundle, MarkdownRenderOptions]:
        """Invoke the CLI with *colophon_flag* (renderer mocked); return the (bundle, options) it received."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        runner: CliRunner = CliRunner()
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.export_roam_tree.render_md") as mock_render_md,
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                        colophon_flag,
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers
        assert result.exit_code == 0, result.output
        call_args = mock_render_md.call_args
        bundle: RenderBundle = call_args.args[0]
        options: MarkdownRenderOptions = call_args.args[4]
        return bundle, options

    def test_colophon_flag_sets_emit_and_stamps_bundle(self, tmp_path: pathlib.Path) -> None:
        """--colophon sets emit_colophon on the options and stamps the bundle with gathered provenance."""
        bundle, options = self._render_call_for_flag(tmp_path, "--colophon")
        assert options.emit_colophon is True
        assert isinstance(bundle.provenance, Provenance)

    def test_no_colophon_flag_disables_emit_and_leaves_bundle_unstamped(self, tmp_path: pathlib.Path) -> None:
        """--no-colophon clears emit_colophon and leaves the bundle's provenance unset (None)."""
        bundle, options = self._render_call_for_flag(tmp_path, "--no-colophon")
        assert options.emit_colophon is False
        assert bundle.provenance is None


def _options_for_flags(tmp_path: pathlib.Path, *flags: str) -> MarkdownRenderOptions:
    """Invoke the CLI with *flags* (renderer mocked); return the render options it received.

    The shared harness for flag-plumbing tests: the full CLI path runs (Typer parsing, options
    assembly) while the renderer is mocked, so each test asserts only what landed on the options.
    """
    fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
        anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
    )
    node_tree = article1_node_tree()
    all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
    mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
    runner: CliRunner = CliRunner()
    with (
        patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
        patch("guffin.cli.export_roam_tree.render_md") as mock_render_md,
    ):
        saved_handlers = logging.root.handlers[:]
        logging.root.handlers.clear()
        try:
            result = runner.invoke(
                app,
                [
                    "[[Test Article]] 1",
                    "--port",
                    "3333",
                    "--graph",
                    "SCFH",
                    "--token",
                    "tok",
                    "--output-dir",
                    str(tmp_path),
                    "--no-bundle",
                    *flags,
                ],
            )
        finally:
            logging.root.handlers = saved_handlers
    assert result.exit_code == 0, result.output
    options: MarkdownRenderOptions = mock_render_md.call_args.args[4]
    return options


class TestExportRoamTreeCodeSources:
    """The --code-sources/--no-code-sources flag plumbs emit_code_sources onto the render options.

    Turning the option into an attribution line in the output is the render layer's job and is
    covered there (``tests/render/test_md_rendering.py``); mocking the renderer keeps this
    flag-plumbing check fast while still exercising the full CLI path.
    """

    def test_code_sources_flag_sets_emit(self, tmp_path: pathlib.Path) -> None:
        """--code-sources sets emit_code_sources on the options."""
        assert _options_for_flags(tmp_path, "--code-sources").emit_code_sources is True

    def test_default_omits_code_sources(self, tmp_path: pathlib.Path) -> None:
        """Without the flag, emit_code_sources defaults off."""
        assert _options_for_flags(tmp_path).emit_code_sources is False


class TestExportRoamTreeRenderAlternatives:
    """The --render-alternatives/--no-render-alternatives flag plumbs render_alternatives onto the options."""

    def test_render_alternatives_flag_sets_option(self, tmp_path: pathlib.Path) -> None:
        """--render-alternatives sets render_alternatives on the options."""
        assert _options_for_flags(tmp_path, "--render-alternatives").render_alternatives is True

    def test_default_omits_alternatives(self, tmp_path: pathlib.Path) -> None:
        """Without the flag, render_alternatives defaults off."""
        assert _options_for_flags(tmp_path).render_alternatives is False


class TestExportRoamTreeDefaultPdfRender:
    """The --default-pdf-render flag plumbs the untagged-embed placement override onto the options.

    Resolving the override against authored tags and the built-in default matrix is the render
    layer's job and is covered there (``tests/render/test_pdf_placement.py``); this checks only
    the CLI plumbing.
    """

    def test_flag_sets_the_override(self, tmp_path: pathlib.Path) -> None:
        """--default-pdf-render lands its placement on the options."""
        options = _options_for_flags(tmp_path, "--default-pdf-render", "external-link")
        assert options.default_pdf_render is PdfRenderPlacement.EXTERNAL_LINK

    def test_default_is_unset(self, tmp_path: pathlib.Path) -> None:
        """Without the flag, the override is unset and the built-in default matrix decides."""
        assert _options_for_flags(tmp_path).default_pdf_render is None


class TestExportRoamTreeVerifyCodeSources:
    """The --verify-code-sources/--no-verify-code-sources flag gates the export-time GitHub check."""

    def _invoke(self, tmp_path: pathlib.Path, *flags: str) -> tuple[Result, MagicMock]:
        """Invoke the CLI with *flags* (renderer and verifier mocked); return (result, verifier mock)."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        runner: CliRunner = CliRunner()
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.export_roam_tree.render_md"),
            patch("guffin.cli.code_source_verification.verify_code_sources", return_value=()) as mock_verify,
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                        *flags,
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers
        return result, mock_verify

    def test_verification_runs_by_default(self, tmp_path: pathlib.Path) -> None:
        """Without a flag, verification runs on the fetched content."""
        result, mock_verify = self._invoke(tmp_path)
        assert result.exit_code == 0, result.output
        mock_verify.assert_called_once()

    def test_no_verify_flag_skips_the_check(self, tmp_path: pathlib.Path) -> None:
        """--no-verify-code-sources skips the verifier entirely (the offline path)."""
        result, mock_verify = self._invoke(tmp_path, "--no-verify-code-sources")
        assert result.exit_code == 0, result.output
        mock_verify.assert_not_called()

    def test_verification_failure_aborts_with_exit_1(self, tmp_path: pathlib.Path) -> None:
        """A verification failure logs each finding and aborts the export with exit code 1."""
        result, mock_verify = self._invoke(tmp_path)
        assert result.exit_code == 0
        finding = CodeSourceFinding(
            uid="code00001",
            url="https://github.com/psf/requests/blob/main/setup.py",
            diagnosis=CodeSourceDiagnosis.DRIFT,
            detail="the source has moved on",
        )
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes") as mock_fetch,
            patch("guffin.cli.export_roam_tree.render_md") as mock_render,
            patch("guffin.cli.code_source_verification.verify_code_sources", return_value=(finding,)),
        ):
            fetch_spec = NodeFetchSpec(anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True)
            node_tree = article1_node_tree()
            all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
            mock_fetch.return_value = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
            runner: CliRunner = CliRunner()
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers
        assert result.exit_code == 1
        mock_render.assert_not_called()


class TestExportRoamTreeProfile:
    """The CLI resolves the profile from the --type and the fetched content (see resolve_profile).

    ``[[Test Article]] 1`` carries no ``element-type:: part`` headings, so a book export resolves
    to the chapters-at-level-1 profile; the parts upgrade itself is unit-tested in
    ``tests/cli/test_common.py``.  Mocking the renderer keeps these plumbing checks fast — no
    Pandoc subprocess — while still exercising the full CLI path.
    """

    def _profile_for_args(self, tmp_path: pathlib.Path, extra_args: list[str]) -> ProjectProfile:
        """Invoke the CLI with *extra_args* (renderer mocked); return the profile it received."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        runner: CliRunner = CliRunner()
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.export_roam_tree.render_md") as mock_render_md,
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    [
                        "[[Test Article]] 1",
                        "--port",
                        "3333",
                        "--graph",
                        "SCFH",
                        "--token",
                        "tok",
                        "--output-dir",
                        str(tmp_path),
                        "--no-bundle",
                        *extra_args,
                    ],
                )
            finally:
                logging.root.handlers = saved_handlers
        assert result.exit_code == 0, result.output
        profile: ProjectProfile = mock_render_md.call_args.args[1]
        return profile

    def test_book_type_without_part_content_keeps_chapter_division(self, tmp_path: pathlib.Path) -> None:
        """--type book on partless content yields the chapters-at-level-1 book profile."""
        profile = self._profile_for_args(tmp_path, ["--type", "book"])
        assert isinstance(profile, BookProfile)
        assert profile.with_parts is False
        assert profile.structural_policy.top_level_division is TopLevelDivision.CHAPTER

    def test_default_type_yields_default_profile(self, tmp_path: pathlib.Path) -> None:
        """--type article resolves to the (non-book) article profile."""
        profile = self._profile_for_args(tmp_path, ["--type", "article"])
        assert not isinstance(profile, BookProfile)


class TestExportRoamTreeVersion:
    """Tests for the --version flag."""

    def test_version_flag_prints_the_package_version_and_exits(self) -> None:
        """--version answers alone — no target or connection arguments required."""
        result = CliRunner().invoke(app, ["--version"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"guffin {importlib.metadata.version('guffin')}"


def _noted_bundle(*, with_notes_heading: bool, shared_lead_in: bool = False, numbered: bool = False) -> RenderBundle:
    """A one-chapter page citing two notes, with or without a Notes section.

    With *shared_lead_in*, both notes share a lead-in; with *numbered*, their labels are the
    Footnotes extension's numbers rather than phrases.
    """

    def note_link(lead_in: str, uid: str) -> str:
        return f"[{lead_in}]({vertex_link_url(uid, VertexLinkKind.NOTE)})"

    first_lead_in: Final[str] = "1" if numbered else "a phrase"
    second_lead_in: Final[str] = "2" if numbered else "a phrase" if shared_lead_in else "another phrase"
    root_children: Final[list[str]] = ["chap00001", *(["notesh001"] if with_notes_heading else [])]
    vertices: Final[list[Vertex]] = [
        PageVertex(uid="page00001", title="Noted", children=root_children),
        HeadingVertex(uid="chap00001", text="Chapter", heading_level=1, children=["text00001", "notes0001"]),
        TextVertex(
            uid="text00001",
            text=f"{note_link(first_lead_in, 'note00001')} and {note_link(second_lead_in, 'note00002')}.",
        ),
        NotesVertex(uid="notes0001", children=["note00001", "note00002"]),
        TextVertex(uid="note00001", text="First note."),
        TextVertex(uid="note00002", text="Second note."),
    ]
    if with_notes_heading:
        link: Final[VertexLink] = VertexLink(kind=VertexLinkKind.REFERENCE, uid="abc123xyz")
        tag: Final[AttributeAssignment] = AttributeAssignment(
            attribute=AttributeInstance(
                definition=Attribute(name="element-type", domain=AttributeDomain.GUFFIN), link=link
            ),
            values=(LiteralValue(value="endnotes"),),
        )
        vertices.append(HeadingVertex(uid="notesh001", text="Notes", heading_level=1, attribute_assignments=[tag]))
    return RenderBundle(content=VertexTree(tree_vertices=vertices), view={})


class TestExportNoteChecks:
    """export-roam-tree runs the note checks that need the project type before rendering."""

    @staticmethod
    def _export(
        bundle: RenderBundle, project_type: str, tmp_path: pathlib.Path, *extra_args: str
    ) -> tuple[Result, MagicMock]:
        """Export *bundle* as *project_type* with the fetch stubbed and rendering mocked out."""
        render: Final[MagicMock] = MagicMock()
        with patch("guffin.cli.export_roam_tree.fetch_render_bundle", return_value=bundle):
            with patch("guffin.cli.export_roam_tree._render", render):
                saved_handlers = logging.root.handlers[:]
                logging.root.handlers.clear()
                try:
                    result: Result = CliRunner().invoke(
                        app,
                        [
                            "Noted",
                            "--port",
                            "3333",
                            "--graph",
                            "SCFH",
                            "--token",
                            "tok",
                            "--output-dir",
                            str(tmp_path),
                            "--type",
                            project_type,
                            "--no-colophon",
                            *extra_args,
                        ],
                    )
                finally:
                    logging.root.handlers = saved_handlers
        return result, render

    def test_note_ref_underline_reaches_the_pdf_options(self, tmp_path: pathlib.Path) -> None:
        """--no-note-ref-underline reaches the PDF render options; by default the lead-ins are underlined."""
        bundle: Final[RenderBundle] = _noted_bundle(with_notes_heading=True)
        _default, default_render = self._export(bundle, "book", tmp_path, "--format", "pdf")
        result, render = self._export(bundle, "book", tmp_path, "--format", "pdf", "--no-note-ref-underline")
        assert result.exit_code == 0, result.output
        assert default_render.call_args.args[5].note_ref_underline
        assert not render.call_args.args[5].note_ref_underline

    def test_note_options_reach_the_renderer(self, tmp_path: pathlib.Path) -> None:
        """--note-form and --notes-only reach the render options; notes-only adds a '.notes' stem segment."""
        result, render = self._export(
            _noted_bundle(with_notes_heading=True), "book", tmp_path, "--note-form", "short", "--notes-only"
        )
        assert result.exit_code == 0, result.output
        out_file_stem: Final[str] = render.call_args.args[2]
        options: Final[MarkdownRenderOptions] = render.call_args.args[5]
        assert out_file_stem == "Noted.book.notes"
        assert options.note_form is NoteForm.SHORT
        assert options.notes_only

    def test_defaults_are_full_notes_and_the_whole_document(self, tmp_path: pathlib.Path) -> None:
        """Without the options, the full notes render in the whole document, under the plain stem."""
        result, render = self._export(_noted_bundle(with_notes_heading=True), "book", tmp_path)
        assert result.exit_code == 0, result.output
        assert render.call_args.args[2] == "Noted.book"
        assert render.call_args.args[5].note_form is NoteForm.FULL
        assert not render.call_args.args[5].notes_only

    def test_notes_only_without_notes_aborts(self, tmp_path: pathlib.Path) -> None:
        """A notes-only export of a work with no notes and no Notes section has nothing to show, and aborts."""
        page: Final[PageVertex] = PageVertex(uid="page00001", title="Noted", children=["text00001"])
        bundle: Final[RenderBundle] = RenderBundle(
            content=VertexTree(tree_vertices=[page, TextVertex(uid="text00001", text="No notes here.")]), view={}
        )
        result, render = self._export(bundle, "article", tmp_path, "--notes-only")
        assert result.exit_code == 1
        render.assert_not_called()

    def test_notes_only_numbered_notes_aborts(self, tmp_path: pathlib.Path) -> None:
        """An article numbers its notes, so it has no Notes section to export alone."""
        result, render = self._export(_noted_bundle(with_notes_heading=True), "article", tmp_path, "--notes-only")
        assert result.exit_code == 1
        render.assert_not_called()

    def test_noted_book_with_notes_section_renders(self, tmp_path: pathlib.Path) -> None:
        """A book whose notes have a Notes section passes both checks."""
        result, render = self._export(_noted_bundle(with_notes_heading=True), "book", tmp_path)
        assert result.exit_code == 0, result.output
        render.assert_called_once()

    def test_shared_lead_in_in_one_section_aborts(self, tmp_path: pathlib.Path) -> None:
        """Two notes in one section sharing a lead-in abort the export."""
        bundle: Final[RenderBundle] = _noted_bundle(with_notes_heading=True, shared_lead_in=True)
        result, render = self._export(bundle, "book", tmp_path)
        assert result.exit_code == 1
        render.assert_not_called()

    def test_book_without_notes_section_aborts(self, tmp_path: pathlib.Path) -> None:
        """A book that cites notes but has no Notes section aborts the export."""
        result, render = self._export(_noted_bundle(with_notes_heading=False), "book", tmp_path)
        assert result.exit_code == 1
        render.assert_not_called()

    @pytest.mark.parametrize("project_type", ["article", "manuscript"])
    def test_numbered_notes_need_no_notes_section(self, tmp_path: pathlib.Path, project_type: str) -> None:
        """An article or manuscript numbers its notes, so it renders without a Notes section."""
        result, render = self._export(_noted_bundle(with_notes_heading=False), project_type, tmp_path)
        assert result.exit_code == 0, result.output
        render.assert_called_once()
        assert render.call_args.args[1].structural_policy.note_style is NoteStyle.NUMBERED

    def test_numbered_labels_pass_for_numbered_notes(self, tmp_path: pathlib.Path) -> None:
        """An article's notes need no lead-ins, so the extension's numbered labels pass."""
        result, render = self._export(_noted_bundle(with_notes_heading=False, numbered=True), "article", tmp_path)
        assert result.exit_code == 0, result.output
        render.assert_called_once()

    def test_numbered_labels_abort_a_book(self, tmp_path: pathlib.Path) -> None:
        """A book's invisible endnotes are keyed by lead-in, so numbered labels abort the export."""
        result, render = self._export(_noted_bundle(with_notes_heading=True, numbered=True), "book", tmp_path)
        assert result.exit_code == 1
        render.assert_not_called()

    def test_suppressed_notes_skip_the_book_checks(self, tmp_path: pathlib.Path) -> None:
        """With the notes suppressed, a book with numbered labels and no Notes section exports (Q10)."""
        result, render = self._export(
            _noted_bundle(with_notes_heading=False, numbered=True), "book", tmp_path, "--suppress-notes"
        )
        assert result.exit_code == 0, result.output
        render.assert_called_once()
        assert render.call_args.args[5].suppress_notes

    def test_notes_are_rendered_by_default(self, tmp_path: pathlib.Path) -> None:
        """Without the option, the notes are not suppressed."""
        result, render = self._export(_noted_bundle(with_notes_heading=True), "book", tmp_path)
        assert result.exit_code == 0, result.output
        assert not render.call_args.args[5].suppress_notes

    def test_suppress_notes_with_notes_only_aborts(self, tmp_path: pathlib.Path) -> None:
        """A notes-only export that suppresses its notes would have nothing to show, so it aborts."""
        result, render = self._export(
            _noted_bundle(with_notes_heading=True), "book", tmp_path, "--notes-only", "--suppress-notes"
        )
        assert result.exit_code == 1
        render.assert_not_called()

    def test_suppressed_notes_skip_the_fetch_note_checks(self, tmp_path: pathlib.Path) -> None:
        """The fetch pipeline is asked to skip its note checks when the notes are suppressed."""
        fetch: Final[MagicMock] = MagicMock(return_value=_noted_bundle(with_notes_heading=True))
        with patch("guffin.cli.export_roam_tree.fetch_render_bundle", fetch):
            with patch("guffin.cli.export_roam_tree._render", MagicMock()):
                saved_handlers = logging.root.handlers[:]
                logging.root.handlers.clear()
                try:
                    result: Result = CliRunner().invoke(
                        app,
                        [
                            *("Noted", "--port", "3333", "--graph", "SCFH", "--token", "tok"),
                            *("--output-dir", str(tmp_path), "--no-colophon", "--suppress-notes"),
                        ],
                    )
                finally:
                    logging.root.handlers = saved_handlers
        assert result.exit_code == 0, result.output
        assert fetch.call_args.kwargs["check_notes"] is False
