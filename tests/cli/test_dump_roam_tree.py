"""Unit tests for guffin.cli.dump_roam_tree."""

import importlib.metadata
import logging
import pathlib
from typing import Final
from unittest.mock import MagicMock, patch

from conftest import article1_node_tree
from typer.testing import CliRunner, Result

from guffin.cli.dump_roam_tree import app
from guffin.roam.node_fetch_result import NodeFetchAnchor, NodeFetchResult, NodeFetchSpec


class TestDumpRoamTreeVerifyCodeSources:
    """The --verify-code-sources/--no-verify-code-sources flag gates the advisory GitHub check.

    Verification here is advisory — findings warn, the dump always renders and exits 0.
    Turning findings into warnings is exercised with the verifier mocked (its real behavior
    is covered in ``tests/test_code_source_verification.py``); the tree rendering is mocked
    too, keeping these flag-plumbing checks fast.
    """

    def _invoke(self, tmp_path: pathlib.Path, *flags: str) -> tuple[Result, MagicMock]:
        """Invoke the CLI with *flags* (fetch, renderer, and verifier mocked); return (result, verifier mock)."""
        fetch_spec: Final[NodeFetchSpec] = NodeFetchSpec(
            anchor=NodeFetchAnchor(qualifier="[[Test Article]] 1"), include_refs=True
        )
        node_tree = article1_node_tree()
        all_nodes = list(node_tree.tree_network) + list(node_tree.refs_by_id.values())
        mock_result: Final[NodeFetchResult] = NodeFetchResult.from_network(all_nodes, fetch_spec, raw_result=[[{}]])
        runner: CliRunner = CliRunner()
        with (
            patch("guffin.cli.common.FetchRoamNodes.fetch_roam_nodes", return_value=mock_result),
            patch("guffin.cli.dump_roam_tree.dump_trees"),
            patch("guffin.cli.code_source_verification.verify_code_sources", return_value=()) as mock_verify,
        ):
            saved_handlers = logging.root.handlers[:]
            logging.root.handlers.clear()
            try:
                result = runner.invoke(
                    app,
                    ["[[Test Article]] 1", "--port", "3333", "--graph", "SCFH", "--token", "tok", *flags],
                )
            finally:
                logging.root.handlers = saved_handlers
        return result, mock_verify

    def test_verification_runs_by_default_and_stays_advisory(self, tmp_path: pathlib.Path) -> None:
        """Without a flag, the advisory verification runs and the dump exits 0."""
        result, mock_verify = self._invoke(tmp_path)
        assert result.exit_code == 0, result.output
        mock_verify.assert_called_once()

    def test_no_verify_flag_skips_the_check(self, tmp_path: pathlib.Path) -> None:
        """--no-verify-code-sources skips the verifier entirely (the offline path)."""
        result, mock_verify = self._invoke(tmp_path, "--no-verify-code-sources")
        assert result.exit_code == 0, result.output
        mock_verify.assert_not_called()

    def test_no_render_bundle_skips_the_check(self, tmp_path: pathlib.Path) -> None:
        """Without the render bundle there is no vertex tree to verify against."""
        result, mock_verify = self._invoke(tmp_path, "--no-render-bundle")
        assert result.exit_code == 0, result.output
        mock_verify.assert_not_called()


class TestDumpRoamTreeVersion:
    """Tests for the --version flag."""

    def test_version_flag_prints_the_package_version_and_exits(self) -> None:
        """--version answers alone — no target or connection arguments required."""
        result = CliRunner().invoke(app, ["--version"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"guffin {importlib.metadata.version('guffin')}"
