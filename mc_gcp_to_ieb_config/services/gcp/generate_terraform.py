import yaml

from mc_gcp_to_ieb_config.utils.jinja import render_template
from mc_gcp_to_ieb_config.utils.config import get_pantropy_path, validate_config
from pathlib import Path


def module_exists(file_path: str, module_name: str) -> bool:
    """Check if a Terraform module with the given name exists."""
    try:
        with open(file_path, "r") as tf:
            content = tf.read()
            return f'module "{module_name}"' in content
    except (IOError, OSError) as e:
        print(f"Error reading Terraform module file {file_path}: {e}")
        return False


def iam_binding_exists(file_path: str, resource_name: str) -> bool:
    """Check if a Terraform IAM binding resource with the given name exists."""
    try:
        with open(file_path, "r") as tf:
            content = tf.read()
            return f'resource "google_pubsub_topic_iam_member" "{resource_name}"' in content
    except (IOError, OSError) as e:
        print(f"Error reading Terraform file {file_path}: {e}")
        return False


def render_terraform(stream, direction: str, swimlane: str, environment: str):
    """Constructing context for Terraform jinja template."""
    terraform_context = {
        "direction": direction,
        "swimlane": swimlane,
        "environment": environment,
        "kafka_topic_entity_name": stream["kafka_topic_entity_name"],
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
    iam_context = {
        "kafka_topic_entity_name": stream["kafka_topic_entity_name"],
        "entity_version": stream["entity_version"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
        "pub_sub_topic": get_pub_sub_topic_name(stream, direction, swimlane),
        "member": member,
        "member_index": member_index,
    }

    return render_template(iam_context, "pubsub_iam_binding.j2")


def append_config(stream, direction: str, swimlane: str, environment: str):
    """Appending new Terrform module blocks to Pantropy."""
    config = render_terraform(stream, direction, swimlane, environment)

    terraform_path = get_pantropy_path()
    if environment == "prd":
        output = terraform_path.format(env="prod")
    else:
        output = terraform_path.format(env="staging")

    module_name = f'{stream["level_0"]}_{stream["level_1"]}_{stream["kafka_topic_entity_name"]}_{stream["entity_version"]}__stream'

    if module_exists(output, module_name):
        print(f"No new Terraform modules found")
    else:
        with open(output, "a") as tf:
            tf.write("\n" + config)
            print(f"Appended Terraform module to {output}")


def get_iam_path(environment: str) -> str:
    """Get the path to the IAM terraform file, derived from pantropy_path."""
    terraform_path = get_pantropy_path()
    if environment == "prd":
        base_path = terraform_path.format(env="prod")
    else:
        base_path = terraform_path.format(env="staging")

    # Replace the terraform filename with iam.tf
    return str(Path(base_path).parent / "iam.tf")


def append_iam_bindings(stream, direction: str, swimlane: str, environment: str):
    """Append IAM bindings for publishers to the iam.tf file."""
    # Check if the stream has publishers configured
    publishers = stream.get("publishers", [])
    if not publishers:
        return

    iam_path = get_iam_path(environment)

    for idx, member in enumerate(publishers):
        # Generate resource name for this IAM binding
        resource_name = f'{stream["level_0"]}_{stream["level_1"]}_{stream["kafka_topic_entity_name"]}_{stream["entity_version"]}__publisher_{idx}'

        # Check if this IAM binding already exists
        if iam_binding_exists(iam_path, resource_name):
            continue

        # Render and append the IAM binding
        iam_config = render_iam_binding(stream, direction, swimlane, member, idx)

        with open(iam_path, "a") as tf:
            tf.write("\n" + iam_config)
            print(f"Appended IAM binding for {member} to {iam_path}")


def terraform_sync(base_path: str = "mc_gcp_to_ieb_config/configs"):
    """Iterate through all swimlane directories and append new entries to Pantropy."""
    validate_config()
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
                            if stream.get("skip_terraform_sync"):
                                print(
                                    f"Skipping Terraform sync for {stream['name']} (skip_terraform_sync=true)"
                                )
                                continue

                            append_config(
                                stream=stream,
                                direction=direction,
                                swimlane=swimlane_dir.name,
                                environment=env_dir.name,
                            )

                            # Append IAM bindings for publishers (if specified)
                            append_iam_bindings(
                                stream=stream,
                                direction=direction,
                                swimlane=swimlane_dir.name,
                                environment=env_dir.name,
                            )
                    except Exception as e:
                        print(f"Error loading {config_file}: {e}")
                        continue
