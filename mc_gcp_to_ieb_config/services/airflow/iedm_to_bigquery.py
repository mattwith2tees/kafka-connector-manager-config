import json
import yaml
import re
from pathlib import Path


# Converts camelCase field names to snake_case.  (See: https://stackoverflow.com/a/12867228).
CAMEL_TO_SNAKE = re.compile("((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")

# IEDM to BigQuery data type mapping.
TYPE_MAPPINGS = {
    "amount": "numeric",
    "boolean": "bool",
    "date-time": "string",
    "date": "date",
    "double": "double",
    "email": "string",
    "enum": "string",
    "integer": "int64",
    "long": "int64",
    "map": "string",
    "number": "numeric",
    "object": "record",
    "string": "string",
    "uri": "string",
}


def read_json(path: Path) -> dict:
    """Reads a JSON file into memory."""
    with open(path) as file:
        return json.load(file)


def get_iedm_fields(properties: dict, definitions: dict) -> dict:
    """
    Recursively builds a 'graph' (i.e. nested dictionary) of IEDM fields.

    Args:
        properties (dict):
            A map of field names to field attributes, i.e. the `properties` map in an IEDM
            `entities/*.schema.json` file.  For the initial call, pass in the top-level `properties`
            map.  This function will search and collect all fields in `properties`.  If any `$ref`
            (i.e. nested) types are found, they will be searched by subsequent (recursive) calls to
            this function.

        definitions (dict):
            A map of `$ref` names to `$ref` definitions.  Always pass in the `*.schema.json` file's
            top-level `definitions` map.  Conveniently, this map contains all `$ref` types we need
            to reconstruct the graph.

    Returns:
        dict:
            The fully-assembled 'graph' of IEDM fields for a given entity.  To help with upcoming
            BigQuery conversion, all IEDM fields are 'enriched' with an internal metadata field
            `_type`, which consolidates data type information into a single, centralized field.
    """
    fields = {}

    for name, field in properties.items():

        field["_ref"] = _find_ref(field)
        field["_type"] = _find_type(field)

        if field["_ref"]:
            key = field["_ref"][14:]
            definition = definitions[key]
            field["_fields"] = get_iedm_fields(definition.get("properties", {}), definitions)

        fields[name] = field

    return fields


def _find_ref(field: dict) -> dict:
    """Sometimes the `$ref` field is 'hidden' in another field.  This function moves it up top."""
    if "$ref" in field:
        return field["$ref"]
    elif "oneOf" in field:
        return next(x for x in field["oneOf"] if x != {"type": "null"})["$ref"]
    elif "items" in field and "$ref" in field["items"]:
        return field["items"]["$ref"]


def _find_type(field: dict) -> str:
    """Sometimes the `type` field is 'hidden' in another field.  This function moves it up top."""
    if "_ref" in field and field["_ref"]:
        return "enum" if "enum" in field["_ref"] else "object"
    elif "@semantic_type" in field:
        return field["@semantic_type"]
    elif "format" in field:
        return field["format"]
    elif "type" in field and isinstance(field["type"], str):
        return field["type"]
    elif "type" in field and isinstance(field["type"], list):
        return next(x for x in field["type"] if x != "null")
    elif "items" in field and "type" in field["items"]:
        return field["items"]["type"]
    else:
        raise Exception(f"Failed to determine data type for field:\n{json.dumps(field, indent=4)}")


def get_bigquery_fields(iedm_fields: dict, parent: str = "$") -> list[dict]:
    """
    Converts a 'graph' of IEDM fields to a list of BigQuery fields.

    Note:
        Each BigQuery field can link to a _list_ of child fields, e.g. `field["fields"]`.  Thus,
        the returned `list[dict]` structure is also 'graph-like'.

    Args:
        iedm_fields (dict):
            A fully-assembled 'graph' of IEDM fields, e.g. the output of `get_iedm_fields()`.

        parent (str):
            The parent field's JSON extract path, e.g. `$.grandparent.parent`.

    Returns:
        list[dict]:
            The fully-assembled list of BigQuery fields.  To help with downstream query UX, all IEDM
            field names are converted from camelCase to snake_case.  However, to help with upcoming
            `json_extract` statements, the original (camelCase) JSON paths are preserved in an
            internal metadata field `_json_path`.
    """

    bigquery_fields = []

    for name, iedm_field in iedm_fields.items():

        json_path = parent + "." + name
        bigquery_field = {
            "name": _get_bigquery_field_name(name),
            "type": _get_bigquery_field_type(iedm_field),
            "mode": _get_bigquery_field_mode(iedm_field),
            "description": iedm_field.get("description"),
            "_json_path": json_path,
        }

        if "_fields" in iedm_field:
            bigquery_field["fields"] = get_bigquery_fields(iedm_field["_fields"], json_path)

        bigquery_fields.append(bigquery_field)

    return bigquery_fields


def _get_bigquery_field_name(iedm_field_name: str) -> str:
    """Converts camelCase field names to snake_case."""
    return CAMEL_TO_SNAKE.sub(r"_\1", iedm_field_name).lower()


def _get_bigquery_field_type(iedm_field: dict) -> str:
    """Converts an IEDM field type to a BigQuery field type."""
    _type = iedm_field["_type"]
    _type = _type.split("(")[0]
    return TYPE_MAPPINGS[_type]


def _get_bigquery_field_mode(iedm_field: dict) -> str:
    """Maps an IEDM field to a BigQuery field mode."""
    if iedm_field.get("type") == "array":
        return "repeated"
    elif iedm_field.get("@nullable"):
        return "nullable"
    else:
        return "required"
