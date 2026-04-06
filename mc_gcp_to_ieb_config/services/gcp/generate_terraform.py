import logging
import yaml

from mc_gcp_to_ieb_config.utils.jinja import render_template
from mc_gcp_to_ieb_config.utils.config import get_pantropy_path, validate_config
from pathlib import Path

logger = logging.getLogger(__name__)


def to_snake_case(s: str) -> str:
    """Convert hyphens and dots to underscores for BigQuery-compatible names."""
    return s.replace("-", "_").replace(".", "_")


def module_exists(file_path: str, module_name: str) -> bool:
    """Check if a Terraform module with the given name exists."""
    try:
        with open(file_path, "r") as tf:
            content = tf.read()
            return f'module "{module_name}"' in content
    except (IOError, OSError) as e:
        logger.warning(f"Error reading Terraform module file {file_path}: {e}")
        return False


def iam_binding_exists(file_path: str, resource_name: str) -> bool:
    """Check if a Terraform IAM binding resource with the given name exists."""
    try:
        with open(file_path, "r") as tf:
            content = tf.read()
            return f'resource "google_pubsub_topic_iam_member" "{resource_name}"' in content
    except (IOError, OSError) as e:
        logger.warning(f"Error reading Terraform file {file_path}: {e}")
        return False


def render_terraform(stream, direction: str, swimlane: str, environment: str):
    """Constructing context for Terraform jinja template."""
    entity_name_snake = to_snake_case(stream["kafka_topic_entity_name"])
    terraform_context = {
        "direction": direction,
        "swimlane": swimlane,
        "environment": environment,
        "kafka_topic_entity_name": entity_name_snake,
        "entity_version": stream["entity_version"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
    }

    return render_template(terraform_context, "terraform_module.j2")


def get_pub_sub_topic_name(stream, direction: str, swimlane: str) -> str:
    """Get the Pub/Sub topic name, either from config or auto-generated."""
    if "pub_sub_topic" in stream:
        return stream["pub_sub_topic"]
    # Auto-generate topic name following the standard pattern
    return f"{direction}-{swimlane}-{stream['level_0']}_{stream['level_1']}_{stream['kafka_topic_entity_name']}_{stream['entity_version']}"


def render_iam_binding(stream, direction: str, swimlane: str, member: str, member_index: int):
    """Constructing context for IAM binding jinja template."""
    entity_name_snake = to_snake_case(stream["kafka_topic_entity_name"])
    iam_context = {
        "kafka_topic_entity_name": entity_name_snake,
        "entity_version": stream["entity_version"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
        "pub_sub_topic": get_pub_sub_topic_name(stream, direction, swimlane),
        "member": member,
        "member_index": member_index,
    }

    return render_template(iam_context, "pubsub_iam_binding.j2")


def append_config(stream, direction: str, swimlane: str, environment: str) -> dict:
    """Appending new Terrform module blocks to Pantropy. Returns stats dict."""
    config = render_terraform(stream, direction, swimlane, environment)
    entity_name_snake = to_snake_case(stream["kafka_topic_entity_name"])

    terraform_path = get_pantropy_path()
    if environment == "prd":
        output = terraform_path.format(env="prod")
    else:
        output = terraform_path.format(env="staging")

    module_name = f'{stream["level_0"]}_{stream["level_1"]}_{entity_name_snake}_{stream["entity_version"]}__stream'

    if module_exists(output, module_name):
        logger.debug(f"Module {module_name} already exists, skipping")
        return {"modules_added": 0, "modules_skipped": 1}
    else:
        with open(output, "a") as tf:
            tf.write("\n" + config)
            logger.debug(f"Appended Terraform module {module_name} to {output}")
        return {"modules_added": 1, "modules_skipped": 0}


def get_iam_path(environment: str) -> str:
    """Get the path to the IAM terraform file, derived from pantropy_path."""
    terraform_path = get_pantropy_path()
    if environment == "prd":
        base_path = terraform_path.format(env="prod")
    else:
        base_path = terraform_path.format(env="staging")

    # Replace the terraform filename with iam.tf
    return str(Path(base_path).parent / "iam.tf")


def append_iam_bindings(stream, direction: str, swimlane: str, environment: str) -> dict:
    """Append IAM bindings for publishers to the iam.tf file. Returns stats dict."""
    stats = {"iam_added": 0, "iam_skipped": 0}

    publishers = stream.get("publishers", [])
    if not publishers:
        return stats

    iam_path = get_iam_path(environment)

    entity_name_snake = to_snake_case(stream["kafka_topic_entity_name"])
    for idx, member in enumerate(publishers):
        resource_name = f'{stream["level_0"]}_{stream["level_1"]}_{entity_name_snake}_{stream["entity_version"]}__publisher_{idx}'

        if iam_binding_exists(iam_path, resource_name):
            logger.debug(f"IAM binding {resource_name} already exists, skipping")
            stats["iam_skipped"] += 1
            continue

        iam_config = render_iam_binding(stream, direction, swimlane, member, idx)

        with open(iam_path, "a") as tf:
            tf.write("\n" + iam_config)
            logger.debug(f"Appended IAM binding {resource_name} for {member}")
            stats["iam_added"] += 1

    return stats


def terraform_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """Iterate through all swimlane directories and append new entries to Pantropy."""
    validate_config()
    base = Path(base_path)

    totals = {
        "modules_added": 0,
        "modules_skipped": 0,
        "iam_added": 0,
        "iam_skipped": 0,
        "streams_skipped": 0,
    }

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
                            if stream.get("skip_terraform_sync"):
                                logger.debug(
                                    f"Skipping Terraform sync for {stream['name']} (skip_terraform_sync=true)"
                                )
                                totals["streams_skipped"] += 1
                                continue

                            module_stats = append_config(
                                stream=stream,
                                direction=direction,
                                swimlane=swimlane_dir.name,
                                environment=env_dir.name,
                            )
                            totals["modules_added"] += module_stats["modules_added"]
                            totals["modules_skipped"] += module_stats["modules_skipped"]

                            iam_stats = append_iam_bindings(
                                stream=stream,
                                direction=direction,
                                swimlane=swimlane_dir.name,
                                environment=env_dir.name,
                            )
                            totals["iam_added"] += iam_stats["iam_added"]
                            totals["iam_skipped"] += iam_stats["iam_skipped"]
                    except Exception as e:
                        logger.warning(f"Error loading {config_file}: {e}")
                        continue

    logger.info(
        f"Terraform sync complete: "
        f"{totals['modules_added']} modules added, {totals['modules_skipped']} skipped | "
        f"{totals['iam_added']} IAM bindings added, {totals['iam_skipped']} skipped"
    )
    if totals["streams_skipped"] > 0:
        logger.info(f"{totals['streams_skipped']} streams skipped (skip_terraform_sync=true)")
