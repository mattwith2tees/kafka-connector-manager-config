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
                    except Exception as e:
                        print(f"Error loading {config_file}: {e}")
                        continue
