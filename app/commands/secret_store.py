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



@click.command('verify-secret-store', short_help='Verify the selected internal secret store active health and version.')
@with_appcontext
def verify_secret_store() -> None:
    """Read-only pre-bootstrap gate; not credential, storage or recovery admission."""
    if os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', '').strip() != 'openbao':
        raise click.ClickException('Internal secret store provider is missing or unsupported.')
    endpoint = os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', '').strip()
    if endpoint != 'https://secret-store:8200':
        raise click.ClickException('Internal secret store verification requires the approved private service origin.')
    if not os.getenv('INTEGRATION_OPENBAO_CA_BUNDLE', '').strip():
        raise click.ClickException('Internal secret store verification requires explicit provider CA trust.')
    try:
        OpenBaoClient.verify_internal_active_health(endpoint=endpoint)
    except ValueError as exc:
        raise click.ClickException(
            'Internal secret store verification failed; require approved TLS, active unsealed state and version 2.7.3.'
        ) from exc
    click.echo('Secret store health verification PASS: provider=openbao, version=2.7.3, status=active.')
    click.echo('Health only; storage, image identity, policy, audit, credential and recovery admission remain required.')
