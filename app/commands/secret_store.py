"""Operator-only internal secret store status; no root token or initialization mutation."""

from __future__ import annotations

import os

import click
from flask.cli import with_appcontext

from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient


@click.command('secret-store-status', short_help='Read internal secret store initialization and seal status.')
@with_appcontext
def secret_store_status() -> None:
    """Use only the deployment-selected internal HTTPS endpoint and approved CA."""
    provider = os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', '').strip()
    if provider != 'openbao':
        raise click.ClickException('Internal secret store provider is missing or unsupported.')
    endpoint = os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', '').strip()
    if not endpoint:
        raise click.ClickException('Internal secret store endpoint is not configured.')
    try:
        health = OpenBaoClient.probe_health(endpoint=endpoint)
    except ValueError as exc:
        raise click.ClickException(
            'Internal secret store status unavailable; verify approved endpoint and TLS.'
        ) from exc

    status = health['status']
    initialized = health['initialized']
    sealed = health['sealed']
    click.echo(
        f'Secret store provider={provider}, status={status}, '
        f'initialized={str(initialized).lower()}, sealed={str(sealed).lower()}'
    )
    click.echo('Health observation only; credential and bootstrap readiness are not admitted.')
