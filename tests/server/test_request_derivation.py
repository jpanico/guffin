"""Unit tests for guffin.server.request_derivation."""

import enum
import pathlib
from typing import Annotated, Final

import pytest
import typer
from pydantic import BaseModel, Field, ValidationError

from guffin.server.request_derivation import (
    RequestField,
    RequestFieldKind,
    argv_for_request,
    derived_request_model,
    request_fields_for,
)


class SampleMode(enum.StrEnum):
    """A sample enum exercising enum-valued option derivation."""

    FAST = "fast"
    SLOW = "slow"


def _sample_command(
    target: Annotated[str, typer.Argument(help="the target")],
    size: Annotated[int, typer.Option("--size", "-s", help="a size")] = 3,
    mode: Annotated[SampleMode, typer.Option("--mode")] = SampleMode.FAST,
    banner: Annotated[bool, typer.Option("--banner/--no-banner", "-b/-B")] = True,
    label: Annotated[str | None, typer.Option("--label")] = None,
    out_path: Annotated[pathlib.Path | None, typer.Option("--out-path")] = None,
    plain: Annotated[bool, typer.Option(help="a switch with no declared flags")] = False,
) -> None:
    """Sample command exercising every declaration shape the derivation supports."""


class TestRequestFieldsFor:
    """Tests for request_fields_for."""

    def test_one_field_per_parameter_in_signature_order(self) -> None:
        """Every parameter derives to a field, in signature order."""
        fields = request_fields_for(_sample_command)
        assert [field.name for field in fields] == ["target", "size", "mode", "banner", "label", "out_path", "plain"]

    def test_kinds_follow_declaration_shape(self) -> None:
        """Positional → ARGUMENT, bool option → SWITCH_OPTION, everything else → VALUE_OPTION."""
        kinds = {field.name: field.kind for field in request_fields_for(_sample_command)}
        assert kinds["target"] is RequestFieldKind.ARGUMENT
        assert kinds["banner"] is RequestFieldKind.SWITCH_OPTION
        assert kinds["plain"] is RequestFieldKind.SWITCH_OPTION
        assert kinds["size"] is RequestFieldKind.VALUE_OPTION
        assert kinds["mode"] is RequestFieldKind.VALUE_OPTION

    def test_value_flag_prefers_the_long_spelling(self) -> None:
        """A value option with long and short spellings emits the long one."""
        fields = {field.name: field for field in request_fields_for(_sample_command)}
        assert fields["size"].value_flag == "--size"

    def test_switch_flags_prefer_the_long_pair(self) -> None:
        """A switch with long and short paired spellings emits the long pair."""
        fields = {field.name: field for field in request_fields_for(_sample_command)}
        assert fields["banner"].on_flag == "--banner"
        assert fields["banner"].off_flag == "--no-banner"

    def test_undeclared_switch_synthesizes_the_typer_pair(self) -> None:
        """A bool option with no declared flags derives the pair Typer itself would synthesize."""
        fields = {field.name: field for field in request_fields_for(_sample_command)}
        assert fields["plain"].on_flag == "--plain"
        assert fields["plain"].off_flag == "--no-plain"

    def test_description_carries_the_help_text(self) -> None:
        """A parameter's Typer help text becomes the field's description."""
        fields = {field.name: field for field in request_fields_for(_sample_command)}
        assert fields["target"].description == "the target"
        assert fields["size"].description == "a size"

    def test_excluded_parameters_are_left_out(self) -> None:
        """An excluded parameter name derives no field."""
        fields = request_fields_for(_sample_command, excluded=frozenset({"size", "plain"}))
        assert [field.name for field in fields] == ["target", "mode", "banner", "label", "out_path"]

    def test_unannotated_parameter_is_rejected(self) -> None:
        """A parameter without Typer Annotated metadata is a derivation error."""

        def bare_command(count: int = 1) -> None:
            """Command with a bare (non-Annotated) parameter."""

        with pytest.raises(ValueError, match="Annotated"):
            request_fields_for(bare_command)


class TestRequestFieldInvariants:
    """Tests for the RequestField per-kind flag invariants."""

    def test_value_option_requires_value_flag(self) -> None:
        """A VALUE_OPTION field without a value_flag is rejected at construction."""
        with pytest.raises(ValidationError, match="value_flag"):
            RequestField(name="size", python_type=int, kind=RequestFieldKind.VALUE_OPTION)

    def test_switch_option_requires_both_flags(self) -> None:
        """A SWITCH_OPTION field without both flag spellings is rejected at construction."""
        with pytest.raises(ValidationError, match="on_flag"):
            RequestField(name="banner", python_type=bool, kind=RequestFieldKind.SWITCH_OPTION, on_flag="--banner")


class TestDerivedRequestModel:
    """Tests for derived_request_model."""

    def test_argument_field_is_required(self) -> None:
        """The positional-argument field must be supplied."""
        model = derived_request_model("SampleRequest", request_fields_for(_sample_command))
        with pytest.raises(ValidationError, match="target"):
            model.model_validate({})

    def test_option_fields_default_to_none(self) -> None:
        """Every option field is optional, defaulting to None (meaning: not supplied)."""
        model = derived_request_model("SampleRequest", request_fields_for(_sample_command))
        request = model.model_validate({"target": "X"})
        assert getattr(request, "size") is None
        assert getattr(request, "banner") is None

    def test_unknown_field_is_rejected(self) -> None:
        """An unknown request key fails validation rather than being silently ignored."""
        model = derived_request_model("SampleRequest", request_fields_for(_sample_command))
        with pytest.raises(ValidationError, match="bogus"):
            model.model_validate({"target": "X", "bogus": 1})

    def test_extra_definitions_are_appended_with_their_defaults(self) -> None:
        """An extra definition becomes a model field with its own default."""
        model = derived_request_model(
            "SampleRequest",
            request_fields_for(_sample_command),
            extra_definitions={"width": (int, Field(default=120, description="a width"))},
        )
        request = model.model_validate({"target": "X"})
        assert getattr(request, "width") == 120

    def test_extra_definition_name_collision_is_rejected(self) -> None:
        """An extra definition colliding with a derived field name is a derivation error."""
        with pytest.raises(ValueError, match="collides"):
            derived_request_model(
                "SampleRequest",
                request_fields_for(_sample_command),
                extra_definitions={"size": (int, Field(default=1))},
            )


class TestArgvForRequest:
    """Tests for argv_for_request."""

    _FIELDS: Final[tuple[RequestField, ...]] = request_fields_for(_sample_command)
    _MODEL: Final[type[BaseModel]] = derived_request_model("SampleRequest", _FIELDS)

    def test_omitted_fields_contribute_nothing(self) -> None:
        """A request supplying only the target translates to the bare argument."""
        request = self._MODEL.model_validate({"target": "X"})
        assert argv_for_request(request, self._FIELDS) == ["X"]

    def test_value_option_emits_flag_then_token(self) -> None:
        """A value option emits its long flag followed by the value token."""
        request = self._MODEL.model_validate({"target": "X", "size": 7})
        assert argv_for_request(request, self._FIELDS) == ["X", "--size", "7"]

    def test_enum_value_emits_its_value_not_its_repr(self) -> None:
        """An enum-valued option contributes the member's value string."""
        request = self._MODEL.model_validate({"target": "X", "mode": "slow"})
        assert argv_for_request(request, self._FIELDS) == ["X", "--mode", "slow"]

    def test_switch_true_emits_the_on_spelling(self) -> None:
        """A true switch emits the on flag."""
        request = self._MODEL.model_validate({"target": "X", "banner": True})
        assert argv_for_request(request, self._FIELDS) == ["X", "--banner"]

    def test_switch_false_emits_the_off_spelling(self) -> None:
        """A false switch emits the off flag."""
        request = self._MODEL.model_validate({"target": "X", "banner": False})
        assert argv_for_request(request, self._FIELDS) == ["X", "--no-banner"]

    def test_path_value_emits_its_text(self) -> None:
        """A path-valued option contributes the path's text form."""
        request = self._MODEL.model_validate({"target": "X", "out_path": "/tmp/out"})
        assert argv_for_request(request, self._FIELDS) == ["X", "--out-path", "/tmp/out"]

    def test_tokens_follow_signature_order(self) -> None:
        """A fully populated request emits tokens in signature order."""
        request = self._MODEL.model_validate(
            {"target": "X", "size": 2, "mode": "fast", "banner": False, "label": "L", "plain": True}
        )
        assert argv_for_request(request, self._FIELDS) == [
            "X",
            "--size",
            "2",
            "--mode",
            "fast",
            "--no-banner",
            "--label",
            "L",
            "--plain",
        ]
