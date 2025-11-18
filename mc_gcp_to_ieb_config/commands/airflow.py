import click
from mc_gcp_to_ieb_config.services.airflow.generate_bigquey_schema import (
    airflow_schema_sync,
)


@click.group(name="airflow")
def airflow_group() -> None:
    """Commands to manage all airflow configurations."""
    pass


@click.command(name="sync")
def sync():
    """Sync source-of-truth config into downstream airflow configs."""
    print("eventually, this will sync schemas!")
    airflow_schema_sync()


airflow_group.add_command(sync)
