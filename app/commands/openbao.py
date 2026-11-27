"""Deployment-owned internal OpenBao local registration."""

import os

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory import collect_local_inventory
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import resolve_local_inventory_scope
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import (
    OpenBaoConnectionInput,
    local_provider_enabled,
    register_connection,
)
from app.security.credentials import CredentialEncryptionError


@click.command('register-internal-openbao', short_help='Register the deployment-owned local OpenBao connection.')
@click.option('--cluster-id', required=True)
@click.option('--auth-mount', required=True)
@click.option('--role-id', required=True)
@with_appcontext
def register_internal_openbao(cluster_id: str, auth_mount: str, role_id: str) -> None:
    if not local_provider_enabled():
        raise click.ClickException('Explicit local development is required.')
    endpoint = os.getenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', '')
    if os.getenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER') != 'openbao' or endpoint != 'https://secret-store:8200':
        raise click.ClickException('The approved bundled deployment configuration is required.')
    secret_id = click.prompt('Scoped AppRole SecretID', hide_input=True)
    try:
        row = register_connection(
            OpenBaoConnectionInput('KAORI Internal Secret Store', 'internal', endpoint, cluster_id, auth_mount, role_id, secret_id),
            actor_id=None,
        )
    except (ValueError, SQLAlchemyError, CredentialEncryptionError) as exc:
        raise click.ClickException('Registration failed; verify unique identity, encryption, TLS and AppRole.') from exc
    finally:
        del secret_id
    click.echo(f'Internal OpenBao registered: canonical integration ID {row.integration_instance_id}.')
    click.echo('Connection only; independent authority and operational qualification remain pending.')

@click.command('collect-openbao-inventory', short_help='Collect approved local OpenBao KV v2 metadata only.')
@click.option('--instance-id', type=click.IntRange(min=1), required=True, help='Canonical integration ID.')
@click.option('--mount', required=True, help='Independently approved disposable KV v2 mount.')
@with_appcontext
def collect_openbao_inventory(instance_id: int, mount: str) -> None:
    try:
        scope = resolve_local_inventory_scope(instance_id, mount)
    except (ValueError, SQLAlchemyError) as exc:
        raise click.ClickException('The exact local OpenBao inventory scope is unavailable.') from exc
    token = click.prompt('Scoped non-root metadata inspection token', hide_input=True)
    try:
        result = collect_local_inventory(scope, token=token)
    except (ValueError, SQLAlchemyError, RuntimeError) as exc:
        raise click.ClickException('OpenBao metadata collection failed; review approved scope and provider.') from exc
    finally:
        del token
    click.echo(f'Committed metadata: {result.observed_secret_count} secrets, {result.observed_version_count} versions.')
    click.echo('No secret value, credential authority or host execution admitted.')
