"""ASGI application exposing the Guffin CLI commands as HTTP command endpoints.

Three endpoints:

- ``POST /v1/export`` — invokes ``export-roam-tree`` in process with the request's arguments and
  answers with the exported document as a binary body (a ``.mdbundle`` directory answers as a
  zip archive), carrying ``Content-Length``, an RFC 9530 ``Content-Digest``, and a
  ``Content-Disposition`` download name.
- ``POST /v1/dump`` — invokes ``dump-roam-tree`` in process and answers with the captured
  console rendering in the representation the request selects (plain text, HTML, or SVG).
- ``GET /v1/health`` — liveness, the package version, and the serving code's provenance.

The request body is validated against the command's derived request model
(:mod:`guffin.server.request_models`); a malformed or invalid body answers ``400``.  A response
begins only after the invocation has fully completed: success answers ``200`` with the
document, and a failed invocation answers ``422`` with an RFC 9457 problem-details body whose
``detail`` carries the complete captured error text (log records, standard error, and any
traceback).  A fault in the serving layer itself answers ``500``.  Invocations execute one at a
time behind a process-wide lock; requests queue behind it.

Public symbols:

- :data:`app` — the :class:`~fastapi.FastAPI` application instance.
"""

import importlib.metadata
import json
import logging
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from guffin.cli import dump_roam_tree, export_roam_tree
from guffin.common.provenance import Provenance, gather_provenance
from guffin.server.console_export import CONSOLE_MEDIA_TYPE, ConsoleFormat, console_environment, exported_console
from guffin.server.export_artifact import (
    ArtifactResolutionError,
    ExportArtifact,
    content_digest_header,
    packaged_artifact,
    resolved_artifact_path,
)
from guffin.server.invocation import InvocationResult, invoke_typer_command
from guffin.server.problem_details import problem_response
from guffin.server.request_derivation import argv_for_request
from guffin.server.request_models import (
    DUMP_REQUEST_FIELDS,
    DUMP_REQUEST_MODEL,
    EXPORT_REQUEST_FIELDS,
    EXPORT_REQUEST_MODEL,
)

logger = logging.getLogger(__name__)

_VERSION: Final[str] = importlib.metadata.version("guffin")
"""The installed package version, surfaced by the health endpoint and the OpenAPI document."""

_PROVENANCE: Final[Provenance] = gather_provenance()
"""The serving code's provenance, captured once at startup for the health endpoint."""

_EXPORT_COMMAND: Final[str] = "export-roam-tree"
"""The export command's name, as problem responses and log lines identify it."""

_DUMP_COMMAND: Final[str] = "dump-roam-tree"
"""The dump command's name, as problem responses and log lines identify it."""

_INVOCATION_LOCK: Final[threading.Lock] = threading.Lock()
"""Serializes command invocations: the capture machinery swaps process-global state."""

app: Final[FastAPI] = FastAPI(title="guffin server", version=_VERSION)
"""The ASGI application a server process runs."""


def _request_body_schema(model: type[BaseModel]) -> dict[str, object]:
    """Return the OpenAPI ``requestBody`` extra documenting *model* as an endpoint's JSON body.

    The endpoints read their bodies through the raw :class:`~fastapi.Request` (validation
    against a runtime-derived model cannot be expressed as a parameter annotation), so the body
    schema is attached to the route explicitly.
    """
    return {
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": model.model_json_schema()}},
        }
    }


async def _validated_request(request: Request, model: type[BaseModel], command_name: str) -> BaseModel | JSONResponse:
    """Return *request*'s JSON body validated against *model*, or the ``400`` problem response.

    Args:
        request: The incoming HTTP request.
        model: The derived request model to validate the body against.
        command_name: The command the request addresses, named in any problem response.

    Returns:
        The validated request model instance, or an RFC 9457 ``400`` response when the body is
        not valid JSON or fails model validation.
    """
    try:
        payload: object = await request.json()
    except json.JSONDecodeError as error:
        return problem_response(
            400, "malformed request body", f"request body is not valid JSON: {error}", {"command": command_name}
        )
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        return problem_response(400, "invalid request", str(error), {"command": command_name})


def _target_of(request_model: BaseModel) -> str:
    """Return the request's ``target`` value as text (empty when absent)."""
    return str(getattr(request_model, "target", ""))


def _invocation_problem(command_name: str, target: str, invocation: InvocationResult) -> JSONResponse:
    """Return the ``422`` problem response reporting a failed invocation.

    The ``detail`` member carries the complete captured error text: every log record the
    invocation emitted, its standard error, and any exception traceback.
    """
    sections: Final[list[str]] = [
        text for text in (invocation.log_text, invocation.stderr, invocation.traceback_text or "") if text.strip()
    ]
    detail: Final[str] = "\n".join(sections) or f"{command_name} exited with code {invocation.exit_code}"
    return problem_response(
        422,
        f"{command_name} invocation failed",
        detail,
        {"command": command_name, "target": target, "exit_code": invocation.exit_code},
    )


def _run_export(export_request: BaseModel) -> Response:
    """Invoke ``export-roam-tree`` for *export_request* and return the document or problem response.

    The invocation writes into a per-request temporary output directory; on success the single
    artifact it produced is packaged (a ``.mdbundle`` directory zips) and streamed back, with
    the temporary directory removed after the response completes.
    """
    target: Final[str] = _target_of(export_request)
    output_dir: Final[Path] = Path(tempfile.mkdtemp(prefix="guffin-export-"))
    argv: Final[list[str]] = argv_for_request(export_request, EXPORT_REQUEST_FIELDS) + [
        "--output-dir",
        str(output_dir),
    ]
    with _INVOCATION_LOCK:
        invocation: Final[InvocationResult] = invoke_typer_command(export_roam_tree.app, argv)
    logger.info("%s %r -> exit %d", _EXPORT_COMMAND, target, invocation.exit_code)
    if invocation.exit_code != 0:
        shutil.rmtree(output_dir, ignore_errors=True)
        return _invocation_problem(_EXPORT_COMMAND, target, invocation)
    try:
        artifact: Final[ExportArtifact] = packaged_artifact(resolved_artifact_path(output_dir))
    except ArtifactResolutionError as error:
        shutil.rmtree(output_dir, ignore_errors=True)
        return problem_response(
            500, "artifact resolution failed", str(error), {"command": _EXPORT_COMMAND, "target": target}
        )
    return FileResponse(
        path=artifact.path,
        media_type=artifact.media_type,
        filename=artifact.file_name,
        headers={"Content-Digest": content_digest_header(artifact.path)},
        background=BackgroundTask(shutil.rmtree, str(output_dir), ignore_errors=True),
    )


def _run_dump(dump_request: BaseModel) -> Response:
    """Invoke ``dump-roam-tree`` for *dump_request* and return the rendering or problem response.

    The capture runs under the environment overlay the requested representation needs (width,
    color); the captured standard output is then converted to that representation.
    """
    target: Final[str] = _target_of(dump_request)
    console_format: Final[ConsoleFormat] = ConsoleFormat(getattr(dump_request, "console_format"))
    console_width: Final[int] = int(getattr(dump_request, "console_width"))
    ansi: Final[bool] = bool(getattr(dump_request, "ansi"))
    argv: Final[list[str]] = argv_for_request(dump_request, DUMP_REQUEST_FIELDS)
    with _INVOCATION_LOCK:
        invocation: Final[InvocationResult] = invoke_typer_command(
            dump_roam_tree.app, argv, environment=console_environment(console_format, console_width, ansi)
        )
    logger.info("%s %r -> exit %d", _DUMP_COMMAND, target, invocation.exit_code)
    if invocation.exit_code != 0:
        return _invocation_problem(_DUMP_COMMAND, target, invocation)
    body: Final[str] = exported_console(invocation.stdout, console_format, console_width)
    return Response(content=body, media_type=CONSOLE_MEDIA_TYPE[console_format])


@app.post("/v1/export", openapi_extra=_request_body_schema(EXPORT_REQUEST_MODEL))
async def export_endpoint(request: Request) -> Response:
    """Export a Roam page or node subtree and answer with the exported document."""
    parsed: Final[BaseModel | JSONResponse] = await _validated_request(request, EXPORT_REQUEST_MODEL, _EXPORT_COMMAND)
    if isinstance(parsed, JSONResponse):
        return parsed
    return await run_in_threadpool(_run_export, parsed)


@app.post("/v1/dump", openapi_extra=_request_body_schema(DUMP_REQUEST_MODEL))
async def dump_endpoint(request: Request) -> Response:
    """Dump a Roam page or node subtree and answer with the captured console rendering."""
    parsed: Final[BaseModel | JSONResponse] = await _validated_request(request, DUMP_REQUEST_MODEL, _DUMP_COMMAND)
    if isinstance(parsed, JSONResponse):
        return parsed
    return await run_in_threadpool(_run_dump, parsed)


@app.get("/v1/health")
async def health_endpoint() -> JSONResponse:
    """Answer liveness, the package version, and the serving code's provenance."""
    return JSONResponse({"status": "ok", "version": _VERSION, "provenance": _PROVENANCE.summary()})
