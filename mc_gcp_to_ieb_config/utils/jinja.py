import os
import yaml

from jinja2 import Environment, FileSystemLoader
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_DIR = ROOT_DIR / "resources"

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def render_template(context: dict, template: str):
    template = env.get_template(template)
    return template.render(**context)
