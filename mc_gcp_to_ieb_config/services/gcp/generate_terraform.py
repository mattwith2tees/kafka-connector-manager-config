from utils.jinja import render_template

TERRAFORM_MODULE_FILE = "/<path/to/pantropy/repo>/terraform/data/business-intelligence/mc-domain-events/{env}/table_streams_domain_events.tf"


def module_exists(file_path: str, module_name: str) -> bool:
    """Check if a Terraform module with the given name exists."""
    try:
        with open(file_path, "r") as tf:
            content = tf.read()
            return f'module "{module_name}"' in content
    except (IOError, OSError) as e:
        print(f"Error reading Terraform module file {file_path}: {e}")
        return False


def render_terraform(stream):
    terraform_context = {
        "direction": stream["direction"],
        "swimlane": stream["swimlane"],
        "environment": stream["environment"],
        "kafka_topic_entity_name": stream["kafka_topic_entity_name"],
        "entity_version": stream["entity_version"],
        "level_0": stream["level_0"],
        "level_1": stream["level_1"],
    }

    return render_template(terraform_context, "terraform_module.j2")


def append_config(stream):
    config = render_terraform(stream)

    if stream["environment"] == "prd":
        output = TERRAFORM_MODULE_FILE.format(env="prod")
    else:
        output = TERRAFORM_MODULE_FILE.format(env="staging")

    module_name = f'{stream["level_0"]}_{stream["level_1"]}_{stream["kafka_topic_entity_name"]}_{stream["entity_version"]}__stream'

    if module_exists(output, module_name):
        print(f"No new Terraform modules found")
    else:
        with open(output, "a") as tf:
            tf.write("\n" + config)
            print(f"Appended Terraform module to {output}")


def terraform_sync():
    return
