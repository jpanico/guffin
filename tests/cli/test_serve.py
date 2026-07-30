"""Unit tests for guffin.cli.serve."""

import importlib.metadata

from typer.testing import CliRunner

from guffin.cli.serve import app


class TestServeVersion:
    """Tests for the --version flag."""

    def test_version_flag_prints_the_package_version_and_exits(self) -> None:
        """--version answers without starting a server."""
        result = CliRunner().invoke(app, ["--version"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"guffin {importlib.metadata.version('guffin')}"
