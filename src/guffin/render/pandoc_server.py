"""A persistent ``pandoc-server`` that answers Markdown→Pandoc-JSON conversions without process spawn.

Parsing a Markdown string to the Pandoc JSON AST via the Pandoc CLI costs one process spawn
(~87 ms of pure startup, independent of input size).  When many small documents are parsed in
succession — as a test suite does, one parse per rendered ``VertexTree`` — that fixed startup
dominates.  ``pandoc-server`` keeps the Pandoc runtime warm and answers the same conversion over
HTTP in single-digit milliseconds, producing an identical AST (the only wire difference is a
trailing newline, which JSON parsing ignores).

This module manages a lazily started, per-process server and exposes a single entry point,
:func:`markdown_to_json`, that converts through it **only when opted in** via the
``GUFFIN_PANDOC_SERVER`` environment variable.  When the server is not opted in, is unavailable, or
a conversion errors, the function returns ``None`` — signalling the caller to use its own
conversion path (the Pandoc CLI).  The server is never a default and owns no fallback: production
leaves the flag unset and never touches it; the test harness opts in for its fast inner loop.

Public symbols:

- **Functions**: :func:`markdown_to_json` — convert a Pandoc Markdown string to the Pandoc JSON AST
  string via the persistent server, or ``None`` when the server path is unavailable and the caller
  should fall back.
"""

import atexit
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Final

from pydantic import validate_call

logger = logging.getLogger(__name__)

_ENABLE_ENV_VAR: Final[str] = "GUFFIN_PANDOC_SERVER"
"""Environment variable that opts the process into the ``pandoc-server`` acceleration path."""

_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})
"""Case-insensitive values of :data:`_ENABLE_ENV_VAR` that enable the server path."""

_SERVER_BINARY: Final[str] = "pandoc-server"
"""Name of the persistent-server executable that ships with Pandoc."""

_READY_TIMEOUT_SECONDS: Final[float] = 15.0
"""How long to wait for a freshly spawned server to answer its health probe before giving up."""

_REQUEST_TIMEOUT_SECONDS: Final[float] = 30.0
"""Per-conversion HTTP timeout; a slower response than this falls back to the CLI."""

_lock: Final[threading.Lock] = threading.Lock()
"""Serializes lazy start-up and shutdown of the module-level server within a process."""

_server_base_url: str | None = None
"""Base URL of the running server (e.g. ``http://127.0.0.1:PORT``), or ``None`` when not started."""

_server_process: subprocess.Popen[bytes] | None = None
"""Handle to the running server subprocess, or ``None`` when not started."""

_start_failed: bool = False
"""Set once a start attempt fails, so the process stops retrying and stays on the CLI path."""


def _enabled() -> bool:
    """Return whether the ``pandoc-server`` acceleration path is opted in for this process."""
    return os.environ.get(_ENABLE_ENV_VAR, "").strip().lower() in _TRUTHY


def _free_port() -> int:
    """Return an available localhost TCP port.

    Binds an ephemeral port, reads it back, and releases it.  A small race window remains between
    release and the server binding it; acceptable for the test-acceleration use case, which falls
    back to the CLI if the server fails to come up.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _await_ready(base_url: str) -> bool:
    """Poll the server's ``/version`` endpoint until it answers or the readiness timeout elapses."""
    deadline: Final[float] = time.monotonic() + _READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/version", timeout=1.0) as response:
                if response.status == 200:
                    return True
        except urllib.error.URLError, TimeoutError, ConnectionError:
            time.sleep(0.05)
    return False


def _start_server() -> str | None:
    """Spawn a ``pandoc-server`` on a free port and return its base URL, or ``None`` on failure.

    Registers an :mod:`atexit` shutdown for the spawned process.  Any failure — missing binary,
    spawn error, or readiness timeout — returns ``None`` so the caller falls back to the CLI.
    """
    global _server_process
    executable: Final[str | None] = shutil.which(_SERVER_BINARY)
    if executable is None:
        logger.info("%s not found on PATH; using the Pandoc CLI", _SERVER_BINARY)
        return None
    port: Final[int] = _free_port()
    base_url: Final[str] = f"http://127.0.0.1:{port}"
    try:
        _server_process = subprocess.Popen(
            [executable, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        logger.warning("failed to spawn %s: %s; using the Pandoc CLI", _SERVER_BINARY, error)
        return None
    if not _await_ready(base_url):
        logger.warning(
            "%s did not become ready within %.0fs; using the Pandoc CLI", _SERVER_BINARY, _READY_TIMEOUT_SECONDS
        )
        _stop_server()
        return None
    atexit.register(_stop_server)
    logger.info("started %s at %s", _SERVER_BINARY, base_url)
    return base_url


def _stop_server() -> None:
    """Terminate the running server subprocess, if any, and clear the module-level handles."""
    global _server_process, _server_base_url
    if _server_process is not None:
        _server_process.terminate()
        try:
            _server_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _server_process.kill()
        _server_process = None
    _server_base_url = None


def _server_url() -> str | None:
    """Return the running server's base URL, starting it on first use; ``None`` to use the CLI.

    Honors the opt-in flag and a one-shot start-failure latch, so a process that cannot start a
    server pays the start cost at most once and then stays on the CLI path.
    """
    global _server_base_url, _start_failed
    if not _enabled():
        return None
    with _lock:
        if _server_base_url is not None:
            return _server_base_url
        if _start_failed:
            return None
        _server_base_url = _start_server()
        if _server_base_url is None:
            _start_failed = True
        return _server_base_url


def _server_convert(base_url: str, text: str) -> str:
    """Convert *text* (Pandoc Markdown) to the Pandoc JSON AST string via the running server."""
    payload: Final[bytes] = _json_request_body(text)
    request: Final[urllib.request.Request] = urllib.request.Request(
        f"{base_url}/",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8")


def _json_request_body(text: str) -> bytes:
    """Return the ``pandoc-server`` request body converting *text* from Markdown to Pandoc JSON."""
    return json.dumps({"text": text, "from": "markdown", "to": "json"}).encode("utf-8")


def _disable_server() -> None:
    """Stop the running server and latch the process onto the CLI path for all later conversions."""
    global _start_failed
    with _lock:
        _stop_server()
        _start_failed = True


@validate_call
def markdown_to_json(text: str) -> str | None:
    """Convert a Pandoc Markdown string to the Pandoc JSON AST string via the persistent server.

    Uses a lazily started, per-process ``pandoc-server`` when the ``GUFFIN_PANDOC_SERVER``
    environment variable opts in and the server is available.  Returns ``None`` when the server path
    is not opted in, the server cannot be started, or a conversion errors (after which the process
    latches onto ``None``) — the caller should then fall back to its own conversion path.  When it
    does return a string, that string is the same AST the Pandoc CLI produces, modulo a trailing
    newline that downstream JSON parsing ignores.

    Args:
        text: The Pandoc Markdown text to parse.

    Returns:
        The Pandoc JSON AST representation of *text*, or ``None`` when the server did not handle it.
    """
    base_url: Final[str | None] = _server_url()
    if base_url is None:
        return None
    try:
        return _server_convert(base_url, text)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
        logger.warning("%s conversion failed (%s); signalling caller to fall back", _SERVER_BINARY, error)
        _disable_server()
        return None
