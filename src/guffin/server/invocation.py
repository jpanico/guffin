"""In-process invocation of a Typer command, with structured output capture.

The command runs through Typer's own parsing — defaults and environment-variable fallbacks
resolve exactly as at a terminal — via :class:`typer.testing.CliRunner`, in the current process
(no subprocess).  Everything the invocation emits is captured into an
:class:`InvocationResult`: the exit code, the standard output and standard error text, every
log record the invocation produced (the root logger's handlers are replaced with a capturing
handler for the duration, then restored), and the formatted traceback when the command raised
an exception rather than exiting.

The capture swaps process-global state (the root logger's handlers, plus any environment
overlay applied by the runner), so concurrent invocations must be serialized by the caller.

Public symbols:

- :class:`InvocationResult` — everything one in-process command invocation produced.
- :func:`invoke_typer_command` — run a Typer app in process and capture the result.
"""

import io
import logging
import traceback
from collections.abc import Mapping, Sequence
from typing import Final

import typer
from pydantic import BaseModel, ConfigDict, validate_call
from typer.testing import CliRunner, Result

_LOG_CAPTURE_FORMAT: Final[str] = "%(levelname)s %(name)s: %(message)s"
"""Record format for the per-invocation log capture (level and logger name, no timestamps)."""


class InvocationResult(BaseModel):
    """Everything one in-process command invocation produced.

    Attributes:
        exit_code: The invocation's exit code (0 on success).
        stdout: The captured standard output text.
        stderr: The captured standard error text (e.g. usage errors).
        log_text: Every log record emitted during the invocation, one formatted line each.
        traceback_text: The formatted traceback when the command raised an exception rather
            than exiting; ``None`` otherwise.
    """

    model_config = ConfigDict(frozen=True)

    exit_code: int
    stdout: str
    stderr: str
    log_text: str
    traceback_text: str | None = None


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def invoke_typer_command(
    command_app: typer.Typer,
    argv: Sequence[str],
    environment: Mapping[str, str | None] | None = None,
) -> InvocationResult:
    """Run *command_app* in process with *argv* and return everything it produced.

    Args:
        command_app: The Typer application to invoke.
        argv: The command-line tokens to invoke it with.
        environment: An optional environment overlay applied for the invocation's duration —
            a ``None`` value removes the variable, any other value sets it.

    Returns:
        The :class:`InvocationResult` capturing exit code, output streams, log records, and
        any exception traceback.
    """
    capture_buffer: Final[io.StringIO] = io.StringIO()
    capture_handler: Final[logging.StreamHandler[io.StringIO]] = logging.StreamHandler(capture_buffer)
    capture_handler.setFormatter(logging.Formatter(_LOG_CAPTURE_FORMAT))
    runner: Final[CliRunner] = CliRunner()
    saved_handlers: Final[list[logging.Handler]] = logging.root.handlers[:]
    logging.root.handlers = [capture_handler]
    try:
        result: Final[Result] = runner.invoke(
            command_app,
            list(argv),
            env=dict(environment) if environment is not None else None,
            catch_exceptions=True,
        )
    finally:
        logging.root.handlers = saved_handlers
    traceback_text: str | None = None
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        traceback_text = "".join(traceback.format_exception(result.exception))
    return InvocationResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        log_text=capture_buffer.getvalue(),
        traceback_text=traceback_text,
    )
