"""Derive a wire-request vocabulary from a Typer command signature.

A Typer command declares its whole parameter vocabulary exactly once — parameter names, types,
flag spellings, and help text — as ``Annotated`` metadata on the command function's signature.
This module reads that single declaration back at runtime and derives from it, rather than
duplicating it:

- a :class:`RequestField` per command parameter (:func:`request_fields_for`) — the parameter's
  name, underlying type, and the argv spelling(s) that express it on a command line;
- a Pydantic request model (:func:`derived_request_model`) with one field per
  :class:`RequestField` — every non-positional field optional with a ``None`` default, so an
  omitted field contributes nothing to the argv vector and the command's own default (including
  any environment-variable fallback, resolved where the command runs) applies exactly as at a
  terminal;
- the argv vector (:func:`argv_for_request`) that a populated request instance deterministically
  translates to, in signature order.

Public symbols:

- :class:`RequestFieldKind` — how a request field is expressed on a command line.
- :class:`RequestField` — one command parameter as a wire-request field.
- :func:`request_fields_for` — the :class:`RequestField` sequence a command signature derives to.
- :func:`derived_request_model` — the Pydantic request model a field sequence derives to.
- :func:`argv_for_request` — the argv vector a populated request instance translates to.
"""

import enum
import inspect
import types
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Final, Self, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator, validate_call
from typer.models import ArgumentInfo, OptionInfo, ParameterInfo


class RequestFieldKind(enum.StrEnum):
    """How a request field is expressed on a command line.

    Attributes:
        ARGUMENT: A positional argument — the value stands alone, no flag.
        VALUE_OPTION: A flag followed by a value token (``--format epub``).
        SWITCH_OPTION: A boolean flag pair — the value selects the on or off spelling
            (``--numbering`` / ``--no-numbering``).
    """

    ARGUMENT = "argument"
    VALUE_OPTION = "value-option"
    SWITCH_OPTION = "switch-option"


class RequestField(BaseModel):
    """One command parameter as a wire-request field.

    Carries everything needed to mirror the parameter in a request model (name, underlying
    type, help text) and to translate a supplied value back into argv tokens (kind plus the
    flag spelling(s) for that kind).

    Attributes:
        name: The command parameter's name, verbatim — also the request model's field name.
        python_type: The parameter's underlying type — the first ``Annotated`` argument, a class
            or a union such as ``str | None``.
        kind: How the field is expressed on a command line.
        description: The parameter's help text, when declared.
        value_flag: The flag preceding a :attr:`RequestFieldKind.VALUE_OPTION` value.
        on_flag: The spelling a true :attr:`RequestFieldKind.SWITCH_OPTION` value emits.
        off_flag: The spelling a false :attr:`RequestFieldKind.SWITCH_OPTION` value emits.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    python_type: type[object] | types.UnionType
    kind: RequestFieldKind
    description: str | None = None
    value_flag: str | None = None
    on_flag: str | None = None
    off_flag: str | None = None

    @model_validator(mode="after")
    def _verify_kind_flags(self) -> Self:
        """Verify the flag fields required by :attr:`kind` are present."""
        if self.kind is RequestFieldKind.VALUE_OPTION and self.value_flag is None:
            raise ValueError(f"field {self.name!r}: a value option requires value_flag")
        if self.kind is RequestFieldKind.SWITCH_OPTION and (self.on_flag is None or self.off_flag is None):
            raise ValueError(f"field {self.name!r}: a switch option requires on_flag and off_flag")
        return self


def _kebab_flag(parameter_name: str) -> str:
    """Return the long flag Typer synthesizes for *parameter_name* when no spelling is declared."""
    return "--" + parameter_name.replace("_", "-")


def _is_bool_type(python_type: object) -> bool:
    """Return whether *python_type* is ``bool`` or an optional ``bool`` union."""
    if python_type is bool:
        return True
    return set(get_args(python_type)) == {bool, type(None)}


def _switch_flags(parameter_name: str, param_decls: Sequence[str]) -> tuple[str, str]:
    """Return the ``(on, off)`` spellings of a boolean switch from its declared flags.

    Prefers a long paired declaration (``--x/--no-x``) over a short one (``-x/-X``); with no
    declared flags at all, synthesizes the pair Typer itself would.
    """
    paired: Final[list[str]] = [decl for decl in param_decls if "/" in decl]
    if not paired and param_decls:
        raise ValueError(f"parameter {parameter_name!r}: a boolean option must declare an on/off flag pair")
    if not paired:
        return _kebab_flag(parameter_name), "--no-" + parameter_name.replace("_", "-")
    chosen: Final[str] = next((decl for decl in paired if decl.startswith("--")), paired[0])
    on_flag, off_flag = chosen.split("/", 1)
    return on_flag, off_flag


def _value_flag(parameter_name: str, param_decls: Sequence[str]) -> str:
    """Return the flag that precedes a value option's value token.

    Prefers the first declared long flag, then any declared flag; with no declared flags,
    synthesizes the long flag Typer itself would.
    """
    if not param_decls:
        return _kebab_flag(parameter_name)
    return next((decl for decl in param_decls if decl.startswith("--")), param_decls[0])


def _declared_flags(info: OptionInfo) -> tuple[str, ...]:
    """Return an option's declared flag spellings, read the way Typer reads ``Annotated`` usage.

    In ``Annotated`` usage ``typer.Option`` takes only flag spellings positionally, but its first
    positional lands in the underlying ``OptionInfo``'s ``default`` slot — Typer reads a string
    found there back as the leading flag declaration, and so does this.
    """
    leading: Final[tuple[str, ...]] = (info.default,) if isinstance(info.default, str) else ()
    return (*leading, *(info.param_decls or ()))


def _parameter_info(parameter_name: str, metadata: Sequence[object]) -> ParameterInfo:
    """Return the sole Typer ``ParameterInfo`` among an ``Annotated`` parameter's *metadata*."""
    infos: Final[list[ParameterInfo]] = [meta for meta in metadata if isinstance(meta, ParameterInfo)]
    if len(infos) != 1:
        raise ValueError(f"parameter {parameter_name!r}: expected exactly one Typer ParameterInfo, found {len(infos)}")
    return infos[0]


def _request_field(parameter_name: str, annotation: object) -> RequestField:
    """Return the :class:`RequestField` a single ``Annotated`` command parameter derives to."""
    if get_origin(annotation) is not Annotated:
        raise ValueError(f"parameter {parameter_name!r}: expected an Annotated declaration carrying Typer metadata")
    annotated_args: Final[tuple[object, ...]] = get_args(annotation)
    python_type: Final[object] = annotated_args[0]
    if not isinstance(python_type, type | types.UnionType):
        raise ValueError(f"parameter {parameter_name!r}: unsupported underlying type shape {python_type!r}")
    info: Final[ParameterInfo] = _parameter_info(parameter_name, annotated_args[1:])
    description: Final[str | None] = info.help
    if isinstance(info, ArgumentInfo):
        return RequestField(
            name=parameter_name, python_type=python_type, kind=RequestFieldKind.ARGUMENT, description=description
        )
    if not isinstance(info, OptionInfo):
        raise ValueError(f"parameter {parameter_name!r}: unsupported Typer parameter kind {type(info).__name__}")
    param_decls: Final[Sequence[str]] = _declared_flags(info)
    if _is_bool_type(python_type):
        on_flag, off_flag = _switch_flags(parameter_name, param_decls)
        return RequestField(
            name=parameter_name,
            python_type=python_type,
            kind=RequestFieldKind.SWITCH_OPTION,
            description=description,
            on_flag=on_flag,
            off_flag=off_flag,
        )
    return RequestField(
        name=parameter_name,
        python_type=python_type,
        kind=RequestFieldKind.VALUE_OPTION,
        description=description,
        value_flag=_value_flag(parameter_name, param_decls),
    )


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def request_fields_for(
    command: Callable[..., None], excluded: frozenset[str] = frozenset()
) -> tuple[RequestField, ...]:
    """Return the :class:`RequestField` sequence *command*'s signature derives to, in signature order.

    Args:
        command: A Typer command function whose every parameter is declared ``Annotated`` with
            Typer ``Argument``/``Option`` metadata.
        excluded: Parameter names to leave out of the derived vocabulary.

    Returns:
        One :class:`RequestField` per non-excluded parameter, in signature order.

    Raises:
        ValueError: When a parameter lacks Typer metadata or uses an unsupported declaration
            shape (e.g. a boolean option without an on/off flag pair).
    """
    signature: Final[inspect.Signature] = inspect.signature(command)
    return tuple(
        _request_field(parameter_name, parameter.annotation)
        for parameter_name, parameter in signature.parameters.items()
        if parameter_name not in excluded
    )


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def derived_request_model(
    model_name: str,
    fields: Sequence[RequestField],
    extra_definitions: Mapping[str, tuple[object, object]] | None = None,
) -> type[BaseModel]:
    """Return the Pydantic request model *fields* derive to.

    An :attr:`RequestFieldKind.ARGUMENT` field is required; every other field is optional with a
    ``None`` default, ``None`` meaning "not supplied" (the command's own default applies).
    Unknown keys are rejected (``extra="forbid"``), so a mistyped field name fails validation
    instead of being silently ignored.

    Args:
        model_name: The created model class's name; must be a valid Python identifier.
        fields: The derived fields to mirror, in order.
        extra_definitions: Additional ``{name: (annotation, pydantic Field)}`` entries appended to
            the model — fields with no command-parameter counterpart, never translated to argv.
            A name colliding with a derived field is rejected.

    Returns:
        The created :class:`~pydantic.BaseModel` subclass.

    Raises:
        ValueError: When an extra definition's name collides with a derived field's.
    """
    definitions: Final[dict[str, tuple[object, object]]] = {}
    for field in fields:
        if field.kind is RequestFieldKind.ARGUMENT:
            definitions[field.name] = (field.python_type, Field(default=..., description=field.description))
            continue
        definitions[field.name] = (field.python_type | None, Field(default=None, description=field.description))
    for extra_name, extra_definition in (extra_definitions or {}).items():
        if extra_name in definitions:
            raise ValueError(f"extra field {extra_name!r} collides with a derived command parameter")
        definitions[extra_name] = extra_definition
    # The field-definitions unpack cannot be typed against create_model's named dunder
    # parameters; the exemption is local to this call, whose return this signature declares.
    return create_model(  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
        model_name,
        __config__=ConfigDict(extra="forbid"),
        **definitions,  # pyright: ignore[reportArgumentType]
    )


def _argv_token(value: object) -> str:
    """Return the argv token *value* renders to (an enum contributes its value, not its repr)."""
    if isinstance(value, enum.Enum):
        return str(value.value)
    return str(value)


@validate_call(config=ConfigDict(arbitrary_types_allowed=True))
def argv_for_request(request: BaseModel, fields: Sequence[RequestField]) -> list[str]:
    """Return the argv vector *request* translates to, over *fields* in order.

    A field whose request value is ``None`` (or absent from the model entirely) contributes no
    tokens, deferring to the command's own default resolution.  Model fields with no
    :class:`RequestField` counterpart are ignored.

    Args:
        request: A populated instance of a model derived via :func:`derived_request_model`.
        fields: The derived fields to translate, in the order their tokens should appear.

    Returns:
        The argv token list, ready to hand to an in-process command invocation.
    """
    argv: Final[list[str]] = []
    for field in fields:
        value: object = getattr(request, field.name, None)
        if value is None:
            continue
        if field.kind is RequestFieldKind.ARGUMENT:
            argv.append(_argv_token(value))
        elif field.kind is RequestFieldKind.SWITCH_OPTION:
            argv.append(str(field.on_flag) if value else str(field.off_flag))
        else:
            argv.extend((str(field.value_flag), _argv_token(value)))
    return argv
