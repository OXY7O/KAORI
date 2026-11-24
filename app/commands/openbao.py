"""Operator-only internal OpenBao status; no root token or initialization mutation."""

from __future__ import annotations

import os

import click
from flask.cli import with_appcontext

from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient


@click.command('openbao-status', short_help='Read bundled OpenBao initialization and seal status without credentials.')
@with_appcontext
def openbao_status() -> None:
    """Use only the deployment-selected internal HTTPS endpoint and approved CA."""
    endpoint = os.getenv('KAORI_INTERNAL_OPENBAO_ENDPOINT', '').strip()
    if not endpoint:
        raise click.ClickException('Internal OpenBao endpoint is not configured.')
    try:
        health = OpenBaoClient.probe_health(endpoint=endpoint)
    except ValueError as exc:
        raise click.ClickException('Internal OpenBao status unavailable; verify approved endpoint and TLS.') from exc

    status = health['status']
    initialized = health['initialized']
    sealed = health['sealed']
    click.echo(f'OpenBao status={status}, initialized={str(initialized).lower()}, sealed={str(sealed).lower()}')
    click.echo('Health observation only; credential and bootstrap readiness are not admitted.')
