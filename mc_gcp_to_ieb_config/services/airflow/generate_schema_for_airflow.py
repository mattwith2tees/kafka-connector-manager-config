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


def guess_iedm_schema_file(
    level_0: str, level_1: str, kafka_topic: str, kafka_topic_entity_name: str, entity_version: str
) -> str:
    # Only underscores
    level_0 = level_0.replace("-", "_").replace("\.", "_")
    level_1 = level_1.replace("-", "_").replace("\.", "_")
    kafka_topic = kafka_topic.replace("-", "_").replace("\.", "_")
    kafka_topic_entity_name = kafka_topic_entity_name.replace("-", "_").replace("\.", "_")
    # kafka topic will be [prd|stage]_L0_L1_[Ln_]EntityName_version
    # Assuming the format: L0/L1/[Ln/]entities/EntityName.schema.json
    try:
        index_of_l1_end = kafka_topic.index(level_1) + len(level_1)
        index_of_entity_name = kafka_topic.index(kafka_topic_entity_name)
    except ValueError:
        raise ValueError(
            f"The L1 or entity name were not found in the kafka topic, we can't guess the iedm schema location, you'll need to fill out the iedm_schema_location_override config for this domain event: {kafka_topic_entity_name}"
        )
    schema_path = f"{level_0}/{level_1}"
    for x in kafka_topic[index_of_l1_end:index_of_entity_name].split("_"):
        if x != "":
            schema_path = f"{schema_path}/{x}"
    schema_path = f"{schema_path}/entities/{snake_to_camel(kafka_topic_entity_name)}.schema.json"
    return schema_path


def guess_events_table_id(
    env: str, dataset: str, level_0: str, level_1: str, kafka_topic_entity_name: str, version: str
) -> str:
    """I think it's L1_L2_entity_name_version"""
    project = "mc-domain-events-prod" if env == "prd" else "mc-domain-events-staging"
    level_0 = level_0.replace("-", "_").replace(".", "_").lower()
    level_1 = level_1.replace("-", "_").replace(".", "_").lower()
    kafka_topic_entity_name = kafka_topic_entity_name.replace("-", "_").replace(".", "_").lower()
    return f"{project}.{dataset}.{level_0}_{level_1}_{kafka_topic_entity_name}_{version}"


def snake_to_camel(s: str) -> str:
    # foo_bar to FooBar
    return "".join([x.capitalize() for x in s.split("_")])


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
                            if materialization_config.get("iedm_schema_location_override"):
                                iedm_schema_file_location = materialization_config.get(
                                    "iedm_schema_location_override"
                                )
                            else:
                                iedm_schema_file_location = guess_iedm_schema_file(
                                    stream.get("level_0"),
                                    stream.get("level_1"),
                                    stream.get("kafka_topic"),
                                    stream.get("kafka_topic_entity_name"),
                                    stream.get("entity_version"),
                                )

                            iedm_schema_file = find_iedm_schema_file(iedm_schema_file_location)
                            iedm_json = read_json(iedm_schema_file)
                            fields = get_iedm_fields(
                                iedm_json["properties"], iedm_json["definitions"]
                            )
                            primary_keys = iedm_json["@uniqueIdentifierProperties"]
                            bigquery_fields = get_bigquery_fields(fields)
                            write_to_airflow_directory(bigquery_fields, iedm_schema_file_location)
                            events_table_id = guess_events_table_id(
                                env,
                                swimlane_dir.name,
                                stream.get("level_0"),
                                stream.get("level_1"),
                                stream.get("kafka_topic_entity_name"),
                                stream.get("entity_version"),
                            )
                            table_config = {
                                "materialized_table_name": stream.get("name"),
                                "events_table_id": events_table_id,
                                "schema_path": get_relative_airflow_schema_path(
                                    iedm_schema_file_location
                                ),
                                "primary_keys": primary_keys,
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
                print(f"wrote config file: {af.name}")
