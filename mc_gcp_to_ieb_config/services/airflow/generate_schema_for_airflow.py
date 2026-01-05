import yaml
import re
import json
import os
from pathlib import Path
from mc_gcp_to_ieb_config.services.airflow.iedm_to_bigquery import (
    read_json,
    get_iedm_fields,
    get_bigquery_fields,
)

BASE_PATH = "/Users/nhoffman/Projects"
IEDM_SCHEMAJSON_FOLDER = f"{BASE_PATH}/iedm-schema/idp-artifacts/jsonschema/intuit/iedm/datamap"
AIRFLOW_FOLDER = f"{BASE_PATH}/airflow-cloud"
AIRFLOW_SCHEMA_ROOT = f"{BASE_PATH}/airflow-cloud/dags/core/domain_event_materializer/schemas"


def find_iedm_schema_file(path: str) -> str:
    # TODO - find some other, better place for this
    assert Path(BASE_PATH).is_dir()
    assert Path(IEDM_SCHEMAJSON_FOLDER).is_dir()
    assert Path(AIRFLOW_FOLDER).is_dir()
    return f"{IEDM_SCHEMAJSON_FOLDER}/{path}"


def write_to_airflow_directory(bigquery_fields: dict, original_iedm_path: str):
    directory = get_airflow_directory_to_write_schema(original_iedm_path)
    os.makedirs(directory, exist_ok=True)
    filename = get_filename(original_iedm_path)
    with open(f"{directory}/{filename}", "w", encoding="utf-8") as f:
        json.dump(bigquery_fields, f, ensure_ascii=True, indent=4)
        print(f"Wrote: {directory}/{filename}")


def get_airflow_relative_directory_to_write_schema(original_iedm_path: str):
    return re.sub(r"/\w*.schema.json", "", original_iedm_path)


def get_airflow_directory_to_write_schema(original_iedm_path: str):
    return f"{AIRFLOW_SCHEMA_ROOT}/{get_airflow_relative_directory_to_write_schema(original_iedm_path)}"


def get_airflow_materializer_config(env: str):
    return f"{AIRFLOW_FOLDER}/dags/core/domain_event_materializer/config-{env}.yaml"


def get_relative_airflow_schema_path(original_iedm_path: str):
    return f"{get_airflow_relative_directory_to_write_schema(original_iedm_path)}/{get_filename(original_iedm_path)}"


def get_filename(original_iedm_path: str):
    match = re.search(r"/(\w*).schema.json", original_iedm_path)
    return f"{match.group(1)}.json"


def airflow_schema_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """Iterate through all swimlane directories and add relevant BigQuery schemas to airflow-cloud"""
    base = Path(base_path)

    tables_to_materialize = {"e2e": [], "prd": []}

    for swimlane_dir in base.iterdir():
        for env_dir in swimlane_dir.iterdir():
            config_file = env_dir / "ingest.yaml"
            env = env_dir.parts[-1]
            if config_file.exists():
                with open(config_file, "r") as f:
                    config = yaml.safe_load(f) or {}

                    streams = config.get("streams")
                    if not isinstance(streams, list) or not streams:
                        continue

                    for stream in streams:
                        materialization_config = stream.get("materialization")
                        if materialization_config and materialization_config.get("enabled") == True:
                            iedm_schema_file = find_iedm_schema_file(
                                materialization_config.get("iedm_schema")
                            )
                            iedm_json = read_json(iedm_schema_file)
                            fields = get_iedm_fields(
                                iedm_json["properties"], iedm_json["definitions"]
                            )
                            bigquery_fields = get_bigquery_fields(fields)
                            write_to_airflow_directory(
                                bigquery_fields, materialization_config.get("iedm_schema")
                            )
                            table_config = {
                                "materialized_table_name": stream.get("name"),
                                "events_table_id": materialization_config.get("events_table_id"),
                                "schema_path": get_relative_airflow_schema_path(
                                    materialization_config.get("iedm_schema")
                                ),
                                "primary_keys": materialization_config.get("primary_keys"),
                            }
                            if materialization_config.get("create_lookback_window_days"):
                                table_config["create_lookback_window_days"] = (
                                    materialization_config.get("create_lookback_window_days")
                                )
                            if materialization_config.get("timestamp_format"):
                                table_config["timestamp_format"] = (
                                    materialization_config.get("timestamp_format"),
                                )

                            tables_to_materialize[env].append(table_config)

    for env in ("e2e", "prd"):
        with open(get_airflow_materializer_config(env), "w") as af:
            if len(tables_to_materialize[env]):
                airflow_config = {"tables_to_materialize": tables_to_materialize[env]}
                yaml.safe_dump(airflow_config, af, sort_keys=False)
