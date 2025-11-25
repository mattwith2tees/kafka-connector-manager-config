import click
from mc_gcp_to_ieb_config.services.kafka.generate_connector_config import kafka_sync


@click.group(name="kafka")
def kafka_group() -> None:
    """Commands to manage all Kafka Connect configurations."""
    pass


@click.command(name="sync")
def sync():
    """Sync source-of-truth config into downstream Kafka Connector configs."""
    kafka_sync()


kafka_group.add_command(sync)
