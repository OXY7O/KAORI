"""Deployment-owned internal OpenBao local registration."""

import os

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

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
