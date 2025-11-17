from jinja2 import Environment, FileSystemLoader
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def render_template(context: dict, template: str):
    if template == "terraform_module.j2":
        TEMPLATE_DIR = ROOT_DIR / "templates" / "terraform"
    else:
        TEMPLATE_DIR = ROOT_DIR / "templates" / "kafka"

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    rendered_template = env.get_template(template)
    return rendered_template.render(context)
