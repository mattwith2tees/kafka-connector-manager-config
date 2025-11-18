from mc_gcp_to_ieb_config.services.airflow.generate_bigquey_schema import read_json, get_bigquery_fields, get_iedm_fields


TEST_DATA_DIR = "./mc_gcp_to_ieb_config/services/airflow/tests/test_data"

def test_get_iedm_schema():
    file = read_json(f"{TEST_DATA_DIR}/Attribution.schema.json")
    fields = get_iedm_fields(file['properties'], file['definitions'])
    assert "id" in fields
    assert fields["id"]['type'] == "string"

def test_get_bigquery_fields():
    file = read_json(f"{TEST_DATA_DIR}/Attribution.schema.json")
    fields = get_iedm_fields(file['properties'], file['definitions'])
    bigquery_fields = get_bigquery_fields(fields)
    assert any(x.get("name") == "id" for x in bigquery_fields)
