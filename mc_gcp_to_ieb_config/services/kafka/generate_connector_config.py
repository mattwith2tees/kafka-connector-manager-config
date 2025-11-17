import yaml
import os

from pathlib import Path
from mc_gcp_to_ieb_config.utils.jinja import render_template
from mc_gcp_to_ieb_config.utils.util import get_variant

KAFKA_CONNECTORS_DIR = "/Users/mturner14/Documents/git/mc-gcp-to-ieb/app/mc_gcp_to_ieb/configs/{environment}/{direction}-{variant}/"
KAFKA_CONNECTORS_FILE = "connectors.yaml"


def kafka_config_exists(
    existing_configs: list, new_config: dict, keys: list[str]
) -> bool:
    """Check if a Kafka Connector config already exists."""
    for config in existing_configs:
        if all(config.get(key) == new_config.get(key) for key in keys):
            return True
    return False


def render_kafka_config(stream, direction: str, swimlane: str):
    """Constructing context for Kafka jinja template."""
    # Sink (ingest) connectors require pub_sub_topic, while Source (publish) connectors require pub_sub_subscription
    is_ingest = direction == "ingest"

    kafka_context = {
        "kafka_topic_entity_name": stream["kafka_topic_entity_name"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
        "entity_version": stream["entity_version"],
        "kafka_topic": stream["kafka_topic"],
        "pub_sub_topic": (
            stream.get(
                "pub_sub_topic",
                f"{direction}-{swimlane}-{stream['level_0']}_{stream['level_1']}_{stream['kafka_topic_entity_name']}_{stream['entity_version']}",
            )
            if is_ingest
            else None
        ),
        "pub_sub_subscription": (
            stream.get(
                "pub_sub_subscription",
                f"{direction}-{swimlane}-{stream['level_0']}_{stream['level_1']}_{stream['kafka_topic_entity_name']}_{stream['entity_version']}-to-kafka",
            )
            if not is_ingest
            else None
        ),
        "max_tasks": stream["max_tasks"],
        "schemas_enable": stream["schemas_enable"],
    }

    return yaml.safe_load(render_template(kafka_context, "connector_config.yaml.j2"))


def append_config(stream, direction: str, swimlane: str, environment: str):
    """Appending new Kafka connector configs to mc-gcp-to-ieb config."""
    config = render_kafka_config(stream, direction, swimlane)

    variant = get_variant(swimlane=swimlane)

    kafka_dir = KAFKA_CONNECTORS_DIR.format(
        environment=environment, direction=direction, variant=variant
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

    # unique identifiers to prevent creating duplicated connector configs
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


def kafka_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """Iterate through all swimlane directories and append new entries to connector configs."""
    base = Path(base_path)

    for swimlane_dir in base.iterdir():
        for env_dir in swimlane_dir.iterdir():
            for direction in ["ingest", "publish"]:
                config_file = env_dir / f"{direction}.yaml"
                if config_file.exists():
                    try:
                        with open(config_file, "r") as f:
                            config = yaml.safe_load(f) or {}

                        streams = config.get("streams")
                        if not isinstance(streams, list) or not streams:
                            continue

                        for stream in streams:
                            append_config(
                                stream=stream,
                                direction=direction,
                                swimlane=swimlane_dir.name,
                                environment=env_dir.name,
                            )
                    except Exception as e:
                        print(f"Error loading {config_file}: {e}")
                        continue
