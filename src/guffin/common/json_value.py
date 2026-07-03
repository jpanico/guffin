"""JSON value typing.

Public symbols:

- :type:`JsonValue` — a JSON-serializable value: a primitive, or lists/objects of nested JSON
  values.
"""

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
"""A JSON-serializable value: a primitive, or lists/objects of nested JSON values."""
