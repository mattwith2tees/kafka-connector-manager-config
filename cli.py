import logging
import click

from mc_gcp_to_ieb_config.commands.kafka import kafka_group
from mc_gcp_to_ieb_config.commands.terraform import terraform_group
from mc_gcp_to_ieb_config.commands.materialization import materialization_group

logging.basicConfig(level=logging.INFO)


@click.group()
def cli():
    pass


if __name__ == "__main__":
    cli.add_command(kafka_group)
    cli.add_command(terraform_group)
    cli.add_command(materialization_group)
    cli()
