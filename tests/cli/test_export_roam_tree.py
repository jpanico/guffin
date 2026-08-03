"""Unit tests for guffin.cli.export_roam_tree."""

import importlib.metadata
import logging
import os
import pathlib
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
from typer.testing import CliRunner, Result

from guffin.cli.export_roam_tree import app
from guffin.common.provenance import Provenance
from guffin.common.validation import ValidationError, ValidationResult
from guffin.model.code_source_diagnosis import CodeSourceDiagnosis, CodeSourceFinding
from guffin.model.publishing_semantics import PdfRenderPlacement
from guffin.model.render_bundle import RenderBundle
from guffin.render.project import BookProfile, ProjectProfile, TopLevelDivision
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
