import copy
import dataclasses
import pathlib
from dataclasses import MISSING
from enum import EnumType
from inspect import get_annotations
from types import NoneType, UnionType
from typing import (
    Annotated,
    Any,
    Literal,
    NewType,
    NotRequired,
    Required,
    TypeVar,
    Union,
    get_args,
    get_origin,
    is_typeddict,
)

from clan_lib.api.serde import dataclass_to_dict


class JSchemaTypeError(Exception):
    pass


# Inspect the fields of the parameterized type
def inspect_dataclass_fields(t: type) -> dict[TypeVar, type]:
    """
    Returns a map of type variables to actual types for a parameterized type.
    """
    origin = get_origin(t)
    type_args = get_args(t)
    if origin is None:
        return {}

    type_params = origin.__parameters__
    # Create a map from type parameters to actual type arguments
    type_map = dict(zip(type_params, type_args, strict=False))

    return type_map


def apply_annotations(schema: dict[str, Any], annotations: list[Any]) -> dict[str, Any]:
    """
    Add metadata from typing.annotations to the json Schema.
    The annotations can be a dict, a tuple, or a string and is directly applied to the schema as shown below.
    No further validation is done, the caller is responsible for following json-schema.

    Examples

    ```python
    # String annotation
    Annotated[int, "This is an int"] -> {"type": "integer", "description": "This is an int"}

    # Dict annotation
    Annotated[int, {"minimum": 0, "maximum": 10}] -> {"type": "integer", "minimum": 0, "maximum": 10}

    # Tuple annotation
    Annotated[int, ("minimum", 0)] -> {"type": "integer", "minimum": 0}
    ```
    """
    for annotation in annotations:
        if isinstance(annotation, dict):
            # Assuming annotation is a dict that can directly apply to the schema
            schema.update(annotation)
        elif isinstance(annotation, tuple) and len(annotation) == 2:
            # Assuming a tuple where first element is a keyword (like 'minLength') and the second is the value
            schema[annotation[0]] = annotation[1]
        elif isinstance(annotation, str):
            # String annotations can be used for description
            schema.update({"description": f"{annotation}"})
    return schema


def is_typed_dict(t: type) -> bool:
    return is_typeddict(t)


# Function to get member names and their types
def get_typed_dict_fields(typed_dict_class: type, scope: str) -> dict[str, type]:
    """Retrieve member names and their types from a TypedDict."""
    if not hasattr(typed_dict_class, "__annotations__"):
        msg = f"{typed_dict_class} is not a TypedDict."
        raise JSchemaTypeError(msg, scope)
    return get_annotations(typed_dict_class)


def is_type_in_union(union_type: type | UnionType, target_type: type) -> bool:
    if get_origin(union_type) is UnionType:
        return any(issubclass(arg, target_type) for arg in get_args(union_type))
    return union_type == target_type


def is_total(typed_dict_class: type) -> bool:
    """
    Check if a TypedDict has total=true
    https://typing.readthedocs.io/en/latest/spec/typeddict.html#interaction-with-total-false
    """
    return getattr(typed_dict_class, "__total__", True)  # Default to True if not set


def type_to_dict(
    t: Any, scope: str = "", type_map: dict[TypeVar, type] | None = None
) -> dict:
    if type_map is None:
        type_map = {}
    if t is None:
        return {"type": "null"}

    if dataclasses.is_dataclass(t):
        fields = dataclasses.fields(t)
        properties = {}
        for f in fields:
            if f.name.startswith("_"):
                continue
            assert not isinstance(f.type, str), (
                f"Expected field type to be a type, got {f.type}, Have you imported `from __future__ import annotations`?"
            )
            properties[f.metadata.get("alias", f.name)] = type_to_dict(
                f.type,
                f"{scope} {t.__name__}.{f.name}",  # type: ignore
                type_map,  # type: ignore
            )

        required = set()
        for pn, pv in properties.items():
            if pv.get("type") is not None:
                if "null" not in pv["type"]:
                    required.add(pn)

            elif pv.get("oneOf") is not None:
                if "null" not in [i.get("type") for i in pv.get("oneOf", [])]:
                    required.add(pn)

        required_fields = {
            f.name
            for f in fields
            if f.default is MISSING and f.default_factory is MISSING
        }

        # Find intersection
        intersection = required & required_fields

        return {
            "type": "object",
            "properties": properties,
            "required": list(intersection),
            # Dataclasses can only have the specified properties
            "additionalProperties": False,
        }

    if is_typed_dict(t):
        dict_fields = get_typed_dict_fields(t, scope)
        dict_properties: dict = {}
        dict_required: list[str] = []
        for field_name, field_type in dict_fields.items():
            if (
                not is_type_in_union(field_type, type(None))
                and get_origin(field_type) is not NotRequired
            ) or get_origin(field_type) is Required:
                dict_required.append(field_name)

            dict_properties[field_name] = type_to_dict(
                field_type, f"{scope} {t.__name__}.{field_name}", type_map
            )

        return {
            "type": "object",
            "properties": dict_properties,
            "required": dict_required if is_total(t) else [],
            "additionalProperties": False,
        }

    if type(t) is UnionType:
        return {
            "oneOf": [type_to_dict(arg, scope, type_map) for arg in t.__args__],
        }

    if isinstance(t, TypeVar):
        # if t is a TypeVar, look up the type in the type_map
        # And return the resolved type instead of the TypeVar
        resolved = type_map.get(t)
        if not resolved:
            msg = f"{scope} - TypeVar {t} not found in type_map, map: {type_map}"
            raise JSchemaTypeError(msg)
        return type_to_dict(type_map.get(t), scope, type_map)

    if isinstance(t, NewType):
        origtype = t.__supertype__
        return type_to_dict(origtype, scope, type_map)

    if hasattr(t, "__origin__"):  # Check if it's a generic type
        origin = get_origin(t)
        args = get_args(t)

        if origin is None:
            # Non-generic user-defined or built-in type
            # TODO: handle custom types
            msg = f"{scope} Unhandled Type: "
            raise JSchemaTypeError(msg, origin)

        if origin is Literal:
            # Handle Literal values for enums in JSON Schema
            return {
                "type": "string",
                "enum": list(args),  # assumes all args are strings
            }

        if origin is Annotated:
            base_type, *metadata = get_args(t)
            schema = type_to_dict(base_type, scope)  # Generate schema for the base type
            return apply_annotations(schema, metadata)

        if origin is Union:
            union_types = [type_to_dict(arg, scope, type_map) for arg in t.__args__]
            return {
                "oneOf": union_types,
            }

        if origin in {list, set, frozenset, tuple}:
            return {
                "type": "array",
                "items": type_to_dict(t.__args__[0], scope, type_map),
            }

        # Used to mark optional fields in TypedDict
        # Here we just unwrap the type and return the schema for the inner type
        if origin is NotRequired or origin is Required:
            return type_to_dict(t.__args__[0], scope, type_map)

        if issubclass(origin, dict):
            value_type = t.__args__[1]
            if value_type is Any:
                return {"type": "object", "additionalProperties": True}
            return {
                "type": "object",
                "additionalProperties": type_to_dict(value_type, scope, type_map),
            }
        # Generic dataclass with type parameters
        if dataclasses.is_dataclass(origin):
            # This behavior should mimic the scoping of typeVars in dataclasses
            # Once type_to_dict() encounters a TypeVar, it will look up the type in the type_map
            # When type_to_dict() returns the map goes out of scope.
            # This behaves like a stack, where the type_map is pushed and popped as we traverse the dataclass fields
            new_map = copy.deepcopy(type_map)
            new_map.update(inspect_dataclass_fields(t))
            return type_to_dict(origin, scope, new_map)

        msg = f"{scope} - Error api type not yet supported {t!s}"
        raise JSchemaTypeError(msg)

    if isinstance(t, type):
        if t is str:
            return {"type": "string"}
        if t is int:
            return {"type": "integer"}
        if t is float:
            return {"type": "number"}
        if t is bool:
            return {"type": "boolean"}
        if t is object:
            return {"type": "object"}
        if type(t) is EnumType:
            return {
                "type": "string",
                # Construct every enum value and use the same method as the serde module for converting it into the same literal string
                "enum": [dataclass_to_dict(t(value)) for value in t],  # type: ignore
            }
        if t is Any:
            msg = f"{scope} - Usage of the Any type is not supported for API functions. In: {scope}"
            raise JSchemaTypeError(msg)
        if t is pathlib.Path:
            return {
                # TODO: maybe give it a pattern for URI
                "type": "string",
            }
        if t is dict:
            msg = f"{scope} - Generic 'dict' type not supported. Use dict[str, Any] or any more expressive type."
            raise JSchemaTypeError(msg)

        # Optional[T] gets internally transformed Union[T,NoneType]
        if t is NoneType:
            return {"type": "null"}

        msg = f"{scope} - Basic type '{t!s}' is not supported"
        raise JSchemaTypeError(msg)
    msg = f"{scope} - Type '{t!s}' is not supported"
    raise JSchemaTypeError(msg)
