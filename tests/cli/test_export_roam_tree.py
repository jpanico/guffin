"""Unit tests for guffin.cli.export_roam_tree."""

import logging
import os
import pathlib
import shutil
from typing import Final
from unittest.mock import patch

import pytest
import yaml
from conftest import (
    FIXTURES_MD_DIR,
    FIXTURES_MDBUNDLE_DIR,
    FIXTURES_PDF_DIR,
    FIXTURES_YAML_DIR,
    PDF_CREATION_TIMESTAMP,
    article1_node_tree,
)
from typer.testing import CliRunner

from guffin.cli.export_roam_tree import app
from guffin.common.provenance import Provenance
from guffin.common.validation import ValidationError, ValidationResult
from guffin.model.render_bundle import RenderBundle
from guffin.render.project import BookProfile, ProjectProfile, TopLevelDivision
from guffin.render.render_options import MarkdownRenderOptions
from guffin.roam.local_api import Response as LocalApiResponse
from guffin.roam.node_fetch import RoamNodeNotFoundError
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec
from guffin.transcribe.roam_tree_to_guffin import transcribe


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
        output_file: pathlib.Path = tmp_path / "Test_Article_1.default.md"
        assert output_file.exists()
        expected: str = (FIXTURES_MD_DIR / "test_article_1_expected.md").read_text()
        assert output_file.read_text() == expected


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
        bundle_dir: pathlib.Path = tmp_path / "Test_Article_1.default.mdbundle"
        assert bundle_dir.is_dir()
        assert (bundle_dir / "Test_Article_1.default.md").exists()


class TestExportRoamTreeMdbundleFromRaw:
    """End-to-end test of export_roam_tree --bundle for [[Test Article]] 3, from the raw fetch result."""

    def test_mdbundle_from_raw_result_matches_fixture(self, tmp_path: pathlib.Path) -> None:
        """Exporting the bundle from the recorded raw Datalog response matches the baseline mdbundle.

        Drives the full pipeline offline: the only external boundaries are stubbed.
        ``invoke_action`` (the Local API node fetch) returns the recorded
        ``test_article_3_raw_result.yaml`` wire response, so the real RoamNode parsing,
        tree build, transcription, and bundle rendering all run.  The Cloud Firestore
        asset fetch is avoided by pre-seeding the cache directory with the baseline
        bundle's images — their filenames are the ``<sha256(url)>.<ext>`` cache keys, so
        ``fetch_and_cache_asset`` resolves them as cache hits without any network call.
        Each seeded entry gets its metadata sidecar (a cache entry is a file/sidecar pair),
        recording no original filename so the bundle keeps the cache-key asset names the
        baseline was recorded with.
        """
        raw_result: Final[object] = yaml.safe_load((FIXTURES_YAML_DIR / "test_article_3_raw_result.yaml").read_text())
        api_response: Final[LocalApiResponse.Payload] = LocalApiResponse.Payload(success=True, result=raw_result)

        baseline: Final[pathlib.Path] = FIXTURES_MDBUNDLE_DIR / "Test_Article_3.default.mdbundle"
        cache_dir: Final[pathlib.Path] = tmp_path / "cache"
        cache_dir.mkdir()
        for asset in baseline.iterdir():
            if asset.suffix != ".md":
                shutil.copy(asset, cache_dir / asset.name)
                (cache_dir / f"{asset.stem}.meta.json").write_text('{"original_file_name": null}', encoding="utf-8")

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
                        "[[Test Article]] 3",
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
        actual: Final[pathlib.Path] = output_dir / "Test_Article_3.default.mdbundle"
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
        """Exporting [[Test Article]] 1 as a markdown bundle matches the recorded baseline file-for-file.

        Roam credentials (GUFFIN_ROAM_*) are read from the environment by the CLI.
        """
        baseline: Final[pathlib.Path] = FIXTURES_MDBUNDLE_DIR / "Test_Article_1.default.mdbundle"
        assert baseline.exists(), (
            f"baseline mdbundle missing: {baseline}. Record it with: "
            'python tests/regen_fixtures.py "[[Test Article]] 1" --prefix test_article_1 --mdbundle'
        )
        runner: CliRunner = CliRunner()
        saved_handlers = logging.root.handlers[:]
        logging.root.handlers.clear()
        try:
            result = runner.invoke(
                app,
                ["[[Test Article]] 1", "--output-dir", str(tmp_path), "--format", "markdown", "--bundle"],
            )
        finally:
            logging.root.handlers = saved_handlers

        assert result.exit_code == 0, result.output
        actual: Final[pathlib.Path] = tmp_path / "Test_Article_1.default.mdbundle"
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
        baseline: Final[pathlib.Path] = FIXTURES_PDF_DIR / "Test_Article_1.default.pdf"
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
        actual: Final[pathlib.Path] = tmp_path / "Test_Article_1.default.pdf"
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
        """--type default resolves to the (non-book) default profile."""
        profile = self._profile_for_args(tmp_path, ["--type", "default"])
        assert not isinstance(profile, BookProfile)
