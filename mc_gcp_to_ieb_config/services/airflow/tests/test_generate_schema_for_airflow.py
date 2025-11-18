from mc_gcp_to_ieb_config.services.airflow.generate_schema_for_airflow import (
    get_airflow_directory_to_write_schema,
    get_filename,
    AIRFLOW_SCHEMA_ROOT,
)


def test_get_airflow_directory_to_write_schema():
    assert (
        get_airflow_directory_to_write_schema("foo/bar/Baz.schema.json")
        == f"{AIRFLOW_SCHEMA_ROOT}/foo/bar"
    )


def test_get_filename():
    assert get_filename("foo/bar/Baz.schema.json") == "Baz.json"
