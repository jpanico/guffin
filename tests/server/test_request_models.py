"""Unit tests for guffin.server.request_models."""

import inspect

import pytest
from pydantic import ValidationError

from guffin.cli import dump_roam_tree, export_roam_tree
from guffin.server.console_export import ConsoleFormat
from guffin.server.request_derivation import argv_for_request
from guffin.server.request_models import (
    DEFAULT_CONSOLE_WIDTH,
    DUMP_EXCLUDED_PARAMETERS,
    DUMP_REQUEST_FIELDS,
    DUMP_REQUEST_MODEL,
    EXPORT_EXCLUDED_PARAMETERS,
    EXPORT_REQUEST_FIELDS,
    EXPORT_REQUEST_MODEL,
)


class TestExportRequestModel:
    """Tests for the derived export request vocabulary."""

    def test_one_field_per_command_parameter_minus_exclusions(self) -> None:
        """The derived fields mirror the export command's parameters, minus the exclusions."""
        parameter_names = [
            name
            for name in inspect.signature(export_roam_tree.main).parameters
            if name not in EXPORT_EXCLUDED_PARAMETERS
        ]
        assert [field.name for field in EXPORT_REQUEST_FIELDS] == parameter_names

    def test_output_dir_is_absent(self) -> None:
        """A request naming output_dir is rejected — the server allocates the output directory."""
        with pytest.raises(ValidationError, match="output_dir"):
            EXPORT_REQUEST_MODEL.model_validate({"target": "X", "output_dir": "/tmp"})

    def test_version_is_absent(self) -> None:
        """A request naming version is rejected — the flag is a terminal affordance, not work."""
        with pytest.raises(ValidationError, match="version"):
            EXPORT_REQUEST_MODEL.model_validate({"target": "X", "version": True})

    def test_target_is_required(self) -> None:
        """A request without a target fails validation."""
        with pytest.raises(ValidationError, match="target"):
            EXPORT_REQUEST_MODEL.model_validate({})

    def test_unknown_field_is_rejected(self) -> None:
        """A mistyped field name fails validation rather than being silently ignored."""
        with pytest.raises(ValidationError, match="bogus"):
            EXPORT_REQUEST_MODEL.model_validate({"target": "X", "bogus": True})

    def test_design_doc_worked_example_translates_verbatim(self) -> None:
        """The server-mode design doc's Request→argv example holds."""
        request = EXPORT_REQUEST_MODEL.model_validate(
            {
                "target": "[[Test Article]] 6",
                "output_format": "epub",
                "project_type": "book",
                "numbering": False,
            }
        )
        assert argv_for_request(request, EXPORT_REQUEST_FIELDS) == [
            "[[Test Article]] 6",
            "--format",
            "epub",
            "--type",
            "book",
            "--no-numbering",
        ]


class TestDumpRequestModel:
    """Tests for the derived dump request vocabulary and its console extras."""

    def test_one_field_per_command_parameter_minus_exclusions(self) -> None:
        """The derived fields mirror the dump command's parameters, minus the exclusions."""
        parameter_names = [
            name for name in inspect.signature(dump_roam_tree.main).parameters if name not in DUMP_EXCLUDED_PARAMETERS
        ]
        assert [field.name for field in DUMP_REQUEST_FIELDS] == parameter_names

    def test_version_is_absent(self) -> None:
        """A request naming version is rejected — the flag is a terminal affordance, not work."""
        with pytest.raises(ValidationError, match="version"):
            DUMP_REQUEST_MODEL.model_validate({"target": "X", "version": True})

    def test_console_extras_carry_their_defaults(self) -> None:
        """The console extras default to a plain 120-column text rendering."""
        request = DUMP_REQUEST_MODEL.model_validate({"target": "X"})
        assert getattr(request, "console_format") is ConsoleFormat.TEXT
        assert getattr(request, "console_width") == DEFAULT_CONSOLE_WIDTH
        assert getattr(request, "ansi") is False

    def test_console_extras_never_reach_argv(self) -> None:
        """The console extras are serving-layer fields: they translate to no argv tokens."""
        request = DUMP_REQUEST_MODEL.model_validate(
            {"target": "X", "console_format": "svg", "console_width": 80, "ansi": True}
        )
        assert argv_for_request(request, DUMP_REQUEST_FIELDS) == ["X"]
