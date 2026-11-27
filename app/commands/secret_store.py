"""Operator-only internal secret store status; no root token or initialization mutation."""

from __future__ import annotations

import os

import click
from flask import current_app
from flask.cli import with_appcontext

from app.integrations.secrets_management.secrets_pki.providers.openbao.client import OpenBaoClient
from app.integrations.secrets_management.secrets_pki.providers.openbao.qualification import (
    OpenBaoQualificationTarget,
    inspect_registration_candidate,
)


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
    endpoint = _internal_endpoint()
    try:
        OpenBaoClient.verify_internal_active_health(endpoint=endpoint)
    except ValueError as exc:
        raise click.ClickException(
            'Internal secret store verification failed; require approved TLS, active unsealed state and version 2.7.3.'
        ) from exc
    click.echo('Secret store health verification PASS: provider=openbao, version=2.7.3, status=active.')
    click.echo(
        'Health only; storage, image identity, policy, audit, credential and recovery admission remain required.'
    )


def _internal_endpoint() -> str:
    if os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', '').strip() != 'openbao':
        raise click.ClickException('Internal secret store provider is missing or unsupported.')
    endpoint = os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', '').strip()
    if endpoint != 'https://secret-store:8200':
        raise click.ClickException('Internal secret store verification requires the approved private service origin.')
    if not os.getenv('INTEGRATION_OPENBAO_CA_BUNDLE', '').strip():
        raise click.ClickException('Internal secret store verification requires explicit provider CA trust.')
    return endpoint


@click.command('bootstrap-secret-store', short_help='Inspect the internal Secret Store before governed bootstrap.')
@click.option('--plan', is_flag=True, help='Read-only inspection; no provider or database writes.')
@with_appcontext
def bootstrap_secret_store(plan: bool) -> None:
    """First bootstrap increment: actual metadata inspection, never policy activation."""
    if not plan:
        raise click.ClickException('Only --plan is admitted; bootstrap apply is not available.')
    endpoint = _internal_endpoint()
    try:
        OpenBaoClient.verify_internal_active_health(endpoint=endpoint)
    except ValueError as exc:
        raise click.ClickException('Bootstrap inspection requires verified active internal health.') from exc

    token = click.prompt('Short-lived non-root inspection token', hide_input=True)
    try:
        summary = OpenBaoClient.inspect_internal_bootstrap(endpoint=endpoint, token=token)
    except ValueError as exc:
        raise click.ClickException(
            'Bootstrap inspection denied or unavailable; verify scoped authority and audit.'
        ) from exc
    finally:
        del token
    click.echo(
        'Bootstrap inspection: expected audit configuration=observed, '
        f'KV v2 mounts={summary[0]}, AppRole mounts={summary[1]}.'
    )
    click.echo('PLAN ONLY: no provider writes; mount, policy, identity and runtime admission remain pending.')

@click.command('qualify-openbao', short_help='Inspect a local OpenBao registration candidate without activating it.')
@click.option('--ownership', type=click.Choice(['internal', 'external']), required=True)
@click.option('--endpoint', help='Approved external HTTPS origin; omit for the deployment-owned internal store.')
@click.option('--cluster-id', required=True, help='Expected native cluster UUID from independent operator evidence.')
@click.option('--kv-mount', required=True, help='Independently approved exact KV v2 mount segment.')
@click.option('--auth-mount', required=True, help='Independently approved exact AppRole mount segment.')
@click.option('--audit-mount', required=True, help='Independently approved exact audit device mount segment.')
@with_appcontext
def qualify_openbao(
    ownership: str,
    endpoint: str | None,
    cluster_id: str,
    kv_mount: str,
    auth_mount: str,
    audit_mount: str,
) -> None:
    """Local inspection only: no provider writes, registration, credential use or authorization."""
    if os.getenv('APP_ENV') != 'development' or current_app.config.get('APP_ENV') != 'development':
        raise click.ClickException('OpenBao candidate qualification is restricted to explicit local development.')
    if ownership == 'internal':
        if endpoint is not None:
            raise click.ClickException('The internal endpoint is deployment-owned; omit --endpoint.')
        endpoint = _internal_endpoint()
    elif endpoint is None:
        raise click.ClickException('An approved external HTTPS origin is required.')
    target = OpenBaoQualificationTarget(
        ownership=ownership,
        endpoint=endpoint,
        cluster_id=cluster_id,
        kv_mount=kv_mount,
        auth_mount=auth_mount,
        audit_mount=audit_mount,
    )
    token = click.prompt('Short-lived non-root inspection token', hide_input=True)
    try:
        evidence = inspect_registration_candidate(target, token=token)
    except ValueError as exc:
        raise click.ClickException(
            'OpenBao inspection blocked; review approved TLS, cluster, version, token and exact mounts.'
        ) from exc
    finally:
        del token
    click.echo(f'OpenBao {ownership} candidate: observed active version {evidence.version}.')
    click.echo('Cluster match, bounded token, exact KV v2/AppRole mounts and audit configuration: observed.')
    click.echo(f'Observation reference: {evidence.evidence_ref} at {evidence.observed_at.isoformat()}')
    click.echo('REGISTRATION PENDING: independent identity, policy, audit delivery and human acceptance required.')
