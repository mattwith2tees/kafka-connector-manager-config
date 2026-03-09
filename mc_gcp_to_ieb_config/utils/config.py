"""
Load user-specific configuration from user_config.yaml.
"""

import sys
import yaml
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "user_config.yaml"


def validate_config(check_airflow_and_iedm_paths_present=False) -> None:
    """Check if config file exists. Exit early if not."""
    if not CONFIG_FILE.exists():
        print(f"Error: Config file not found: {CONFIG_FILE}")
        print("Please create user_config.yaml with your local paths. See README.md for details.")
        sys.exit(1)

    if check_airflow_and_iedm_paths_present:
        config_paths = ["airflow_path", "iedm_path"]
        config = load_config()
        for config_path in config_paths:
            if not config.get(config_path):
                print(f"Error: config path not set: {config_path}, please set that in {CONFIG_FILE}")
                sys.exit(1)
            directory = Path(config.get(config_path))
            if not directory.exists():
                print(f"Error: directory: {config.get(config_path)} does not exist for config key {config_path}, please fix that")
                sys.exit(1)



def load_config() -> dict:
    """Load configuration from user_config.yaml file."""
    validate_config()
    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f)


def get_pantropy_path() -> str:
    """Get local path for Pantropy repo."""
    config = load_config()
    return config["pantropy_path"]


def get_mc_gcp_to_ieb_path() -> str:
    """Get local path for mc-gcp-to-ieb repo."""
    config = load_config()
    return config["mc_gcp_to_ieb_path"]


def get_airflow_path() -> str:
    """Get local path for airflow repo"""
    config = load_config()
    return config["airflow_path"]


def get_iedm_path() -> str:
    """Get local path for iedm repo"""
    config = load_config()
    return config["iedm_path"]
