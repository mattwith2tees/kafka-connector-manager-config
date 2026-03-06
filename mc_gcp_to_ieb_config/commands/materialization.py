import click
from mc_gcp_to_ieb_config.services.materialization.generate_schema_for_materialization import (
    airflow_schema_sync,
)


@click.group(name="materialization")
def airflow_group() -> None:
    """Commands to manage all materialization configurations."""
    pass


@click.command(name="sync")
def sync():
    """Sync source-of-truth config into downstream materialization configs."""
    airflow_schema_sync()


airflow_group.add_command(sync)
