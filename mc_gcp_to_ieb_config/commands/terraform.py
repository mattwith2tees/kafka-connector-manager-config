import click
from mc_gcp_to_ieb_config.services.gcp.generate_terraform import terraform_sync


@click.group(name="terraform")
def terraform_group() -> None:
    """Commands to manage all terraform configurations."""
    pass


@click.command(name="sync")
def sync():
    """Sync source-of-truth config into downstream terraform configs."""
    terraform_sync()


terraform_group.add_command(sync)
