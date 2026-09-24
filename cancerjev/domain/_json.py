"""Strict primitives for the scientific JSON boundary, not a domain model."""

import json

from cancerjev.domain.measurements import ContractError, finite, require


def obj(value: object, fields: str | None = None) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ContractError("expected JSON object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ContractError("object key must be text")
        result[key] = item
    if fields is not None:
        require(set(result) == set(fields.split()), f"unexpected/missing fields; expected {fields}")
    return result


def seq(value: object) -> tuple[object, ...]:
    if not isinstance(value, list):
        raise ContractError("expected JSON array")
    return tuple(value)


def string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("expected nonblank text")
    return value


def optional_string(value: object) -> str | None:
    return None if value is None else string(value)


def integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractError("expected integer, not bool")
    return value


def number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ContractError("expected finite number, not bool/null")
    finite(value, "JSON number")
    return float(value)


def boolean(value: object) -> bool:
    if not isinstance(value, bool):
        raise ContractError("expected boolean")
    return value


def string_tuple(value: object) -> tuple[str, ...]:
    return tuple(string(item) for item in seq(value))


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ContractError(f"nonfinite JSON constant: {value}")


def _float(value: str) -> float:
    result = float(value)
    finite(result, "JSON float")
    return result


def decode(data: bytes) -> dict[str, object]:
    if not isinstance(data, bytes):
        raise ContractError("scientific readers require immutable bytes")
    try:
        return obj(json.loads(data, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError("invalid scientific JSON") from exc


def version(record: dict[str, object]) -> int:
    value = record.get("schema_version")
    if type(value) is not int or value not in (1, 2, 3):
        raise ContractError("expected explicit schema_version 1, 2 or 3", "UNSUPPORTED_SCHEMA_VERSION")
    return integer(value)
