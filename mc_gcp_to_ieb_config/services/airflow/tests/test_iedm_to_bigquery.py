from mc_gcp_to_ieb_config.services.airflow.iedm_to_bigquery import (
    read_json,
    get_bigquery_fields,
    get_iedm_fields,
    _find_type,
)

import pytest


TEST_DATA_DIR = "./mc_gcp_to_ieb_config/services/airflow/tests/test_data"

fields_provider = [
    (
        {
            "@classification": "PUBLIC",
            "description": "Globally-unique identifier for a resource.  New ID namespace for IEDM, multi-part encoding. ",
            "type": "string",
        },
        "string",
    ),
    (
        {
            "_ref": "#/definitions/system:types:AlternateId",
            "@classification": "PUBLIC",
            "description": "Other ids: external, internal, relative to the current system",
            "type": "array",
            "items": {
                "$ref": "#/definitions/system:types:AlternateId",
                "@intent": "TYPE",
                "description": "Means of storing a namespace-controlled alternative ID for an entity",
            },
        },
        "object",
    ),
    (
        {
            "@nullable": False,
            "@classification": "RESTRICTED",
            "description": "The value of the extended property field.",
            "@piiClassification": "Non PII",
            "type": "array",
            "items": {"type": "string"},
            "_ref": None,
            "_type": "array",
        },
        "string",
    ),
    (
        {
            "@classification": "RESTRICTED",
            "@piiClassification": "Non PII",
            "@semantic_type": "decimal(38,9)",
            "description": "Total balance on the customer including children balance.",
            "pattern": "^-?[0-9]{0,29}(\\.)?([0-9]{0,9})?$",
            "type": "string",
        },
        "decimal(38,9)",
    ),
]


def test_get_iedm_schema():
    file = read_json(f"{TEST_DATA_DIR}/Attribution.schema.json")
    fields = get_iedm_fields(file["properties"], file["definitions"])
    assert "id" in fields
    assert fields["id"]["type"] == "string"


def test_get_bigquery_fields():
    file = read_json(f"{TEST_DATA_DIR}/Attribution.schema.json")
    fields = get_iedm_fields(file["properties"], file["definitions"])
    bigquery_fields = get_bigquery_fields(fields)
    assert any(x.get("name") == "id" for x in bigquery_fields)


@pytest.mark.parametrize("field,expected", fields_provider)
def test__find_type(field, expected):
    assert _find_type(field) == expected
