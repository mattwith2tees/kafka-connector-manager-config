import yaml
import os

from pathlib import Path
from mc_gcp_to_ieb_config.utils.jinja import render_template
from mc_gcp_to_ieb_config.utils.util import get_variant
from mc_gcp_to_ieb_config.utils.config import get_mc_gcp_to_ieb_path, validate_config

KAFKA_CONNECTORS_FILE = "connectors.yaml"


def to_snake_case(s: str) -> str:
    """Convert hyphens and dots to underscores for BigQuery-compatible names."""
    return s.replace("-", "_").replace(".", "_")


def _truncate_value(value, max_length: int = 50) -> str:
    """Truncate a value for display in logs."""
    if value is None:
        return "None"
    str_val = str(value).replace("\n", " ").strip()
    if len(str_val) > max_length:
        return str_val[:max_length] + "..."
    return str_val


def dump_configs_with_notes(configs: list) -> str:
    """
    Dump configs to YAML string, converting 'note' fields to comments.
    Notes are rendered as comment blocks above each config entry.
    """
    lines = []
    for config in configs:
        # Extract note (don't mutate original config)
        note = config.get("note")
        config_to_dump = {k: v for k, v in config.items() if k != "note"}

        # Add note as comment if present
        if note:
            for note_line in note.strip().split("\n"):
                lines.append(f"# {note_line}")

        # Dump the config entry
        config_yaml = yaml.dump([config_to_dump], sort_keys=False, default_flow_style=False)
        lines.append(config_yaml.rstrip())

    return "\n".join(lines) + "\n"


def get_config_key(config: dict) -> tuple:
    """Generate a unique key for a connector config."""
    return (
        config.get("name"),
        config.get("level_0"),
        config.get("level_1"),
        config.get("entity_version"),
    )


def render_kafka_config(stream, direction: str, swimlane: str):
    """Constructing context for Kafka jinja template."""
    # Sink (ingest) connectors require pub_sub_topic, while Source (publish) connectors require pub_sub_subscription
    is_ingest = direction == "ingest"
    entity_name_snake = to_snake_case(stream["kafka_topic_entity_name"])

    kafka_context = {
        "kafka_topic_entity_name": entity_name_snake,
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
        "entity_version": stream["entity_version"],
        "kafka_topic": stream["kafka_topic"],
        "pub_sub_topic": (
            stream.get(
                "pub_sub_topic",
                f"{direction}-{swimlane}-{stream['level_0']}_{stream['level_1']}_{entity_name_snake}_{stream['entity_version']}",
            )
            if is_ingest
            else None
        ),
        "pub_sub_subscription": (
            stream.get(
                "pub_sub_subscription",
                f"{direction}-{swimlane}-{stream['level_0']}_{stream['level_1']}_{entity_name_snake}_{stream['entity_version']}-to-kafka",
            )
            if not is_ingest
            else None
        ),
        "max_tasks": stream["max_tasks"],
        "schemas_enable": stream["schemas_enable"],
        "headers_publish": stream.get("headers_publish"),
        "note": stream.get("note"),
    }

    return yaml.safe_load(render_template(kafka_context, "connector_config.yaml.j2"))


def sync_connector_configs(source_configs: list, connector_path: str):
    """
    Sync connector configs to the target file.
    - Adds new configs from source
    - Updates existing configs with source values (e.g., max_tasks changes)
    - Removes configs that are no longer in source
    """
    existing = []
    try:
        if os.path.exists(connector_path):
            with open(connector_path, "r") as f:
                existing = yaml.safe_load(f) or []
    except (yaml.YAMLError, IOError) as e:
        print(f"Error reading existing config: {e}")
        raise

    # Build lookup dicts for comparison
    source_by_key = {get_config_key(c): c for c in source_configs}
    existing_by_key = {get_config_key(c): c for c in existing}

    source_keys = set(source_by_key.keys())
    existing_keys = set(existing_by_key.keys())

    # Find configs to add (in source but not in existing)
    to_add = [source_by_key[k] for k in source_keys - existing_keys]

    # Find configs to remove (in existing but not in source)
    to_remove = [existing_by_key[k] for k in existing_keys - source_keys]

    # Find configs to update (exist in both but have different values)
    to_update = []
    for key in source_keys & existing_keys:
        if source_by_key[key] != existing_by_key[key]:
            to_update.append((existing_by_key[key], source_by_key[key]))

    # If no changes needed, skip
    if not to_add and not to_remove and not to_update:
        print(f"No changes needed for {connector_path}")
        return

    # Build final config list from source (this ensures all values are current)
    final_configs = source_configs

    # Write updated config
    try:
        with open(connector_path, "w") as f:
            f.write(dump_configs_with_notes(final_configs))

        if to_remove:
            for c in to_remove:
                print(f"Removed: {c.get('name')} {c.get('entity_version')}")
            print(f"Removed {len(to_remove)} connector(s) from {connector_path}")
        if to_add:
            for c in to_add:
                print(f"Added: {c.get('name')} {c.get('entity_version')}")
            print(f"Added {len(to_add)} connector(s) to {connector_path}")
        if to_update:
            for old, new in to_update:
                # Show what changed (truncate long values for readability)
                changes = []
                for k in set(old.keys()) | set(new.keys()):
                    if old.get(k) != new.get(k):
                        old_val = _truncate_value(old.get(k))
                        new_val = _truncate_value(new.get(k))
                        changes.append(f"{k}: {old_val} → {new_val}")
                print(
                    f"Updated: {new.get('name')} {new.get('entity_version')} ({', '.join(changes)})"
                )
            print(f"Updated {len(to_update)} connector(s) in {connector_path}")
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
                            print(
                                f"Skipping Kafka sync for {stream['name']} (skip_kafka_sync=true)"
                            )
                            continue

                        rendered = render_kafka_config(stream, direction, swimlane_dir.name)
                        configs_by_target[connector_path].append(rendered)

                except Exception as e:
                    print(f"Error loading {config_file}: {e}")
                    continue

    # Sync each target file
    for connector_path, source_configs in configs_by_target.items():
        sync_connector_configs(source_configs, connector_path)
