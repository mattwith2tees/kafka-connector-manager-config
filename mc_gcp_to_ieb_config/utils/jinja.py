from jinja2 import Environment, FileSystemLoader
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"

TEMPLATE_REGISTRY = {
    "terraform_module.j2": "terraform",
    "pubsub_iam_binding.j2": "terraform",
    "connector_config.yaml.j2": "kafka",
}


def render_template(context: dict, template: str) -> str:
    """Render a Jinja2 template with the given context."""
    if template not in TEMPLATE_REGISTRY:
        raise ValueError(
            f"Unknown template: {template}. Expected one of: {list(TEMPLATE_REGISTRY.keys())}"
        )

    template_subdir = TEMPLATE_REGISTRY[template]
    template_dir = TEMPLATES_DIR / template_subdir

    env = Environment(loader=FileSystemLoader(template_dir))
    return env.get_template(template).render(context)
