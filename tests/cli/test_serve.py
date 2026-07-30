"""Unit tests for guffin.cli.serve."""

import importlib.metadata
import logging
from unittest.mock import patch

from starlette.middleware.cors import CORSMiddleware
from typer.testing import CliRunner, Result

from guffin.cli.serve import app
from guffin.server.app import app as asgi_app


def _invoke_without_root_handlers(arguments: list[str], env: dict[str, str] | None = None) -> Result:
    """Invoke the serve CLI with root log handlers cleared for the duration.

    configure_logging() installs a root StreamHandler at import time, and pytest's live-log
    handler also sits on the root logger; a log write during CliRunner's invoke fights the
    runner's stream isolation (closed-stream ValueError).  Temporarily clearing root handlers
    prevents the conflict.
    """
    saved_handlers = logging.root.handlers[:]
    logging.root.handlers.clear()
    try:
        return CliRunner().invoke(app, arguments, env=env)
    finally:
        logging.root.handlers = saved_handlers


class TestServeVersion:
    """Tests for the --version flag."""

    def test_version_flag_prints_the_package_version_and_exits(self) -> None:
        """--version answers without starting a server."""
        result = CliRunner().invoke(app, ["--version"])
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"guffin {importlib.metadata.version('guffin')}"


class TestServeAllowOrigin:
    """Tests for the --allow-origin CORS opt-in."""

    def test_without_the_flag_the_bare_app_is_served(self) -> None:
        """Unset, uvicorn runs the ASGI app itself — no CORS wrap at all."""
        with patch("guffin.cli.serve.uvicorn.run") as run_mock:
            result = _invoke_without_root_handlers([])
        assert result.exit_code == 0, result.output
        assert run_mock.call_args.args[0] is asgi_app

    def test_the_flag_wraps_the_app_with_the_cors_grants(self) -> None:
        """A repeated --allow-origin serves the CORS-wrapped app admitting every named origin."""
        with patch("guffin.cli.serve.uvicorn.run") as run_mock:
            result = _invoke_without_root_handlers(
                ["--allow-origin", "https://roamresearch.com", "--allow-origin", "https://other.example"]
            )
        assert result.exit_code == 0, result.output
        served = run_mock.call_args.args[0]
        assert isinstance(served, CORSMiddleware)
        assert served.allow_origins == ["https://roamresearch.com", "https://other.example"]

    def test_the_env_var_supplies_space_separated_origins(self) -> None:
        """GUFFIN_SERVER_ALLOW_ORIGIN admits each space-separated origin."""
        with patch("guffin.cli.serve.uvicorn.run") as run_mock:
            result = _invoke_without_root_handlers(
                [], env={"GUFFIN_SERVER_ALLOW_ORIGIN": "https://roamresearch.com https://other.example"}
            )
        assert result.exit_code == 0, result.output
        served = run_mock.call_args.args[0]
        assert isinstance(served, CORSMiddleware)
        assert served.allow_origins == ["https://roamresearch.com", "https://other.example"]
