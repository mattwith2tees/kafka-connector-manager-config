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
AIRFLOW_SCHEMA_ROOT = f"{BASE_PATH}/airflow-cloud/dags/core/streaming-materializer/schemas"


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


def get_airflow_directory_to_write_schema(original_iedm_path: str):
    directory = re.sub(r"/\w*.schema.json", "", original_iedm_path)
    return f"{AIRFLOW_SCHEMA_ROOT}/{directory}"


def get_filename(original_iedm_path: str):
    match = re.search(r"/(\w*).schema.json", original_iedm_path)
    return f"{match.group(1)}.json"


def airflow_schema_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """Iterate through all swimlane directories and add relevant BigQuery schemas to airflow-cloud"""
    base = Path(base_path)

    for swimlane_dir in base.iterdir():
        for env_dir in swimlane_dir.iterdir():
            config_file = env_dir / "ingest.yaml"
            if config_file.exists():
                try:
                    with open(config_file, "r") as f:
                        config = yaml.safe_load(f) or {}

                        streams = config.get("streams")
                        if not isinstance(streams, list) or not streams:
                            continue

                        for stream in streams:
                            if stream.get("materialize") == True and stream.get("iedm_schema"):
                                iedm_schema_file = find_iedm_schema_file(stream.get("iedm_schema"))
                                iedm_json = read_json(iedm_schema_file)
                                fields = get_iedm_fields(
                                    iedm_json["properties"], iedm_json["definitions"]
                                )
                                bigquery_fields = get_bigquery_fields(fields)
                                write_to_airflow_directory(
                                    bigquery_fields, stream.get("iedm_schema")
                                )

                except Exception as e:
                    print(f"Error loading {config_file}: {e}")
                    continue
