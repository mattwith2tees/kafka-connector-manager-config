import yaml
import os

from utils.jinja import render_template

KAFKA_CONNECTORS_DIR = "/<path/to/mc-gcp-to-ieb/repo>/app/mc_gcp_to_ieb/configs/{environment}/{direction}-{variant}/"
KAFKA_CONNECTORS_FILE = "connectors.yaml"


def kafka_config_exists(
    existing_configs: list, new_config: dict, keys: list[str]
) -> bool:
    """Check if a Kafka Connector config already exists."""
    for config in existing_configs:
        if all(config.get(key) == new_config.get(key) for key in keys):
            return True
    return False


def render_kafka_config(stream):
    kafka_context = {
        "kafka_topic_entity_name": stream["kafka_topic_entity_name"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
        "entity_version": stream["entity_version"],
        "pub_sub_topic": stream.get(
            "pub_sub_topic",
            f"{stream['direction']}-{stream['swimlane']}-{stream['level_0']}_{stream['level_1']}_{stream['kafka_topic_entity_name']}_{stream['entity_version']}",
        ),
        "max_tasks": stream["max_tasks"],
        "schemas_enable": stream["schemas_enable"],
    }

    return yaml.safe_load(render_template(kafka_context, "connector_config.yaml.j2"))


def append_config(stream):
    config = render_kafka_config(stream)

    kafka_dir = KAFKA_CONNECTORS_DIR.format(
        environment=stream["environment"],
        direction=stream["direction"],
        variant=stream["variant"],
    )
    connector_path = os.path.join(kafka_dir, KAFKA_CONNECTORS_FILE)

    existing = []
    try:
        if os.path.exists(connector_path):
            with open(connector_path, "r") as f:
                existing = yaml.safe_load(f) or []
    except (yaml.YAMLError, IOError) as e:
        print(f"Error reading existing config: {e}")
        raise

    dedupe_keys = ["name", "kafka_topic", "entity_version"]

    if not kafka_config_exists(existing, config, dedupe_keys):
        existing.append(config)
        try:
            with open(connector_path, "w") as f:
                yaml.dump(existing, f, sort_keys=False)
                print(f"Appended connector config to {connector_path}")
        except (yaml.YAMLError, IOError) as e:
            print(f"Error writing connector config: {e}")
            raise
    else:
        print(f"No new Kafka Connector configs found")


def kafka_sync():
    return
