"""Unit tests for guffin.server.invocation."""

import logging
import os
from typing import Annotated, Final

import typer

from guffin.server.invocation import invoke_typer_command

logger = logging.getLogger(__name__)

sample_app: Final[typer.Typer] = typer.Typer()


@sample_app.command()
def sample(mode: Annotated[str, typer.Argument(help="what the command should do")]) -> None:
    """Sample command producing output, log records, and failures by mode."""
    logger.warning("running mode=%s", mode)
    print(f"mode is {mode}")
    if mode == "fail":
        logger.error("deliberate failure")
        raise typer.Exit(code=1)
    if mode == "boom":
        raise RuntimeError("kaboom")
    if mode == "env":
        print(os.environ.get("SAMPLE_VAR", "unset"))


class TestInvokeTyperCommand:
    """Tests for invoke_typer_command."""

    def test_success_captures_exit_code_and_stdout(self) -> None:
        """A clean run reports exit code 0 with its standard output captured."""
        result = invoke_typer_command(sample_app, ["ok"])
        assert result.exit_code == 0
        assert "mode is ok" in result.stdout
        assert result.traceback_text is None

    def test_log_records_are_captured(self) -> None:
        """Log records emitted during the invocation land in log_text, formatted one per line."""
        result = invoke_typer_command(sample_app, ["ok"])
        assert "WARNING" in result.log_text
        assert "running mode=ok" in result.log_text

    def test_failure_captures_exit_code_and_error_records(self) -> None:
        """A typer.Exit(1) run reports exit code 1 with its error records captured, no traceback."""
        result = invoke_typer_command(sample_app, ["fail"])
        assert result.exit_code == 1
        assert "deliberate failure" in result.log_text
        assert result.traceback_text is None

    def test_uncaught_exception_captures_the_traceback(self) -> None:
        """An exception escaping the command is captured as a formatted traceback."""
        result = invoke_typer_command(sample_app, ["boom"])
        assert result.exit_code == 1
        assert result.traceback_text is not None
        assert "RuntimeError: kaboom" in result.traceback_text

    def test_usage_error_reaches_stderr(self) -> None:
        """Argv Typer cannot parse reports through stderr with the usage exit code."""
        result = invoke_typer_command(sample_app, ["ok", "surplus"])
        assert result.exit_code == 2
        assert "Usage" in result.stderr

    def test_environment_overlay_applies_for_the_invocation(self) -> None:
        """An overlay value is visible to the command; a None value removes the variable."""
        overlaid = invoke_typer_command(sample_app, ["env"], environment={"SAMPLE_VAR": "from-overlay"})
        assert "from-overlay" in overlaid.stdout
        removed = invoke_typer_command(sample_app, ["env"], environment={"SAMPLE_VAR": None})
        assert "unset" in removed.stdout

    def test_root_handlers_are_restored(self) -> None:
        """The root logger's handlers are exactly as they were before the invocation."""
        before = logging.root.handlers[:]
        invoke_typer_command(sample_app, ["ok"])
        assert logging.root.handlers == before
