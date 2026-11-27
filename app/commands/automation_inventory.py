"""Explicit disposable inventory/config migration and readback."""

import click
from flask.cli import with_appcontext

from app.infrastructure_automation.kubernetes.inventory_store import (
    LocalInventoryStoreIntent,
    observe_inventory_store,
)


@click.command('automation-inventory-store', short_help='Publish or compare one local Kubespray inventory/config snapshot.')
@click.option('--connection-id', type=click.IntRange(min=1), required=True, help='Canonical Ansible integration ID.')
@click.option('--provider-id', type=click.IntRange(min=1), required=True, help='Canonical OpenBao or Vault integration ID.')
@click.option('--cluster-id', required=True, help='Independently verified native cluster UUID.')
@click.option('--mount', required=True, help='Independently approved local KV v2 mount.')
@click.option('--pod-cidr', required=True)
@click.option('--service-cidr', required=True)
@click.option('--publish', is_flag=True, help='Create immutable version 1; default is read/compare only.')
@with_appcontext
def automation_inventory_store(
    connection_id: int, provider_id: int, cluster_id: str, mount: str, pod_cidr: str, service_cidr: str, publish: bool
) -> None:
    intent = LocalInventoryStoreIntent(connection_id, provider_id, cluster_id, mount, pod_cidr, service_cidr)
    token = click.prompt('Short-lived scoped operator token', hide_input=True)
    try:
        receipt = observe_inventory_store(intent, token=token, publish=publish)
    except Exception as exc:
        raise click.ClickException(
            'Inventory store observation blocked; review scope, current source/hosts, native policy and readback.'
        ) from exc
    finally:
        del token
    click.echo(f"Exact provider inventory readback: version={receipt['version']}, fingerprint={receipt['fingerprint']}")
    click.echo('Historical evidence committed. No host or cluster execution authorized.')
