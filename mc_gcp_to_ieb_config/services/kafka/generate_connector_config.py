import yaml
import os

from pathlib import Path
from mc_gcp_to_ieb_config.utils.jinja import render_template
from mc_gcp_to_ieb_config.utils.util import get_variant
from mc_gcp_to_ieb_config.utils.config import get_mc_gcp_to_ieb_path, validate_config

KAFKA_CONNECTORS_FILE = "connectors.yaml"


def get_config_key(config: dict) -> tuple:
    """Generate a unique key for a connector config."""
    return (config.get("name"), config.get("level_0"), config.get("level_1"), config.get("entity_version"))


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


def sync_connector_configs(source_configs: list, connector_path: str):
    """
    Sync connector configs to the target file.
    - Adds new configs from source
    - Removes configs that are no longer in source
    - Preserves configs that exist in both
    """
    existing = []
    try:
        if os.path.exists(connector_path):
            with open(connector_path, "r") as f:
                existing = yaml.safe_load(f) or []
    except (yaml.YAMLError, IOError) as e:
        print(f"Error reading existing config: {e}")
        raise

    # Build sets of config keys for comparison
    source_keys = {get_config_key(c) for c in source_configs}
    existing_keys = {get_config_key(c) for c in existing}

    # Find configs to add (in source but not in existing)
    to_add = [c for c in source_configs if get_config_key(c) not in existing_keys]
    
    # Find configs to remove (in existing but not in source)
    to_remove = [c for c in existing if get_config_key(c) not in source_keys]
    
    # If no changes needed, skip
    if not to_add and not to_remove:
        print(f"No changes needed for {connector_path}")
        return

    # Build final config list: existing (minus removed) + new
    final_configs = [c for c in existing if get_config_key(c) in source_keys]
    final_configs.extend(to_add)

    # Write updated config
    try:
        with open(connector_path, "w") as f:
            yaml.dump(final_configs, f, sort_keys=False)
        
        if to_remove:
            for c in to_remove:
                print(f"Removed: {c.get('name')} {c.get('entity_version')}")
            print(f"Removed {len(to_remove)} connector(s) from {connector_path}")
        if to_add:
            for c in to_add:
                print(f"Added: {c.get('name')} {c.get('entity_version')}")
            print(f"Added {len(to_add)} connector(s) to {connector_path}")
    except (yaml.YAMLError, IOError) as e:
        print(f"Error writing connector config: {e}")
        raise


def kafka_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """
    Sync source-of-truth configs to downstream Kafka Connector configs.
    
    For each environment/direction combination:
    - Collects all streams from source config
    - Renders connector configs
    - Syncs to target file (adds new, removes deleted, preserves existing)
    """
    validate_config()
    base = Path(base_path)

    # Group streams by (environment, direction, variant) to sync entire files at once
    configs_by_target: dict[str, list] = {}

    for swimlane_dir in base.iterdir():
        if not swimlane_dir.is_dir():
            continue
        for env_dir in swimlane_dir.iterdir():
            if not env_dir.is_dir():
                continue
            for direction in ["ingest", "publish"]:
                config_file = env_dir / f"{direction}.yaml"
                if not config_file.exists():
                    continue
                    
                try:
                    with open(config_file, "r") as f:
                        config = yaml.safe_load(f) or {}

                    streams = config.get("streams")
                    if not isinstance(streams, list) or not streams:
                        continue

                    variant = get_variant(swimlane=swimlane_dir.name)
                    kafka_dir = get_mc_gcp_to_ieb_path().format(
                        environment=env_dir.name, direction=direction, variant=variant
                    )
                    connector_path = os.path.join(kafka_dir, KAFKA_CONNECTORS_FILE)

                    if connector_path not in configs_by_target:
                        configs_by_target[connector_path] = []

                    for stream in streams:
                        if stream.get("skip_kafka_sync"):
                            print(f"Skipping Kafka sync for {stream['name']} (skip_kafka_sync=true)")
                            continue

                        rendered = render_kafka_config(stream, direction, swimlane_dir.name)
                        configs_by_target[connector_path].append(rendered)

                except Exception as e:
                    print(f"Error loading {config_file}: {e}")
                    continue

    # Sync each target file
    for connector_path, source_configs in configs_by_target.items():
        sync_connector_configs(source_configs, connector_path)
