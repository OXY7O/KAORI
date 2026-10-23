"""Bounded GitHub App onboarding service (SC-02 #2741).

Reuses IntegrationInstance and EncryptedText. No route, job, provider module
registration, webhook ingress, or 'Ready' state is introduced here.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field

from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.source_control.source_control.providers.github.auth import _positive_provider_id
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubAppClient,
    GitHubProviderError,
    InstallationReadiness,
)
from app.models.integration import IntegrationInstance
from app.models.source_control import GitHubAppCredential, SourceAccount, SourceInstallation
from app.security.credentials import CredentialEncryptionError


@dataclass(frozen=True, slots=True)
class GitHubConnectionInput:
    """Credentials must never be serialized to JobExecution, logs or templates."""

    name: str
    environment: str
    description: str | None
    app_id: str | int
    installation_id: str | int
    account_id: str | int
    private_key_pem: str = field(repr=False)
    webhook_secret: str = field(repr=False)
    enabled: bool = True


def _verified_ids(values: GitHubConnectionInput) -> tuple[str, str, str]:
    try:
        return (
            str(_positive_provider_id(values.app_id)),
            str(_positive_provider_id(values.installation_id)),
            str(_positive_provider_id(values.account_id)),
        )
    except ValueError as exc:
        raise GitHubProviderError('GitHub App installation/account identity is invalid.') from exc


def _validate_name(name: str) -> str:
    value = str(name or '').strip()
    if len(value) < 2 or len(value) > 160 or any(ord(ch) < 32 for ch in value):
        raise ValueError('GitHub integration name must be between 2 and 160 safe characters.')
    return value


def test_connection(values: GitHubConnectionInput) -> InstallationReadiness:
    """Read-only live probe. Never persists a credential, token or readiness."""
    app_id, installation_id, account_id = _verified_ids(values)
    _validate_name(values.name)
    if not values.private_key_pem or not values.webhook_secret:
        raise GitHubProviderError('GitHub App signing credential and webhook secret are required.')
    return GitHubAppClient(
        app_id=app_id, private_key_pem=values.private_key_pem
    ).validate_installation(installation_id, account_id)


def save_tested_connection(values: GitHubConnectionInput) -> SourceInstallation:
    """Revalidate live grant during save and commit only a non-ready identity.

    A future form may call Test Connection first for UX, but Save does not
    trust a client-side proof or count. This is intentionally a double check.
    No hidden propagation of GitHub App PEM through Celery/job arguments.
    """
    name = _validate_name(values.name)
    if len(str(values.environment or '').strip()) > 40:
        raise ValueError('GitHub integration environment is invalid.')
    if values.description is not None and len(values.description) > 2000:
        raise ValueError('GitHub integration description is too long.')
    app_id, installation_id, account_id = _verified_ids(values)
    observed = test_connection(values)
    if (
        str(observed.app_id) != app_id or str(observed.installation_id) != installation_id
        or str(observed.account_id) != account_id
        or observed.repository_selection not in {'all', 'selected'}
    ):
        raise GitHubProviderError('GitHub App connection evidence does not match the requested installation.')

    duplicate = IntegrationInstance.query.filter_by(
        integration_type='source_control', name=name
    ).first()
    if duplicate is not None:
        raise ValueError('A Source Control connection with that name already exists.')
    previous_installation = SourceInstallation.query.filter_by(
        provider_key='github',
        host_key='github.com',
        native_app_id=app_id,
        native_installation_id=installation_id,
    ).first()
    if previous_installation is not None:
        raise ValueError('GitHub App installation is already registered.')

    try:
        app_credential = GitHubAppCredential.query.filter_by(
            host_key='github.com', native_app_id=app_id
        ).first()
        if app_credential is not None:
            if (
                not app_credential.enabled
                or not hmac.compare_digest(app_credential.private_key_pem, values.private_key_pem)
                or not hmac.compare_digest(app_credential.webhook_secret, values.webhook_secret)
            ):
                raise GitHubProviderError(
                    'GitHub App credential differs from the existing protected registration.'
                )
        else:
            app_credential = GitHubAppCredential(
                host_key='github.com', native_app_id=app_id,
                private_key_pem=values.private_key_pem, webhook_secret=values.webhook_secret,
                enabled=True,
            )
            db.session.add(app_credential)
            db.session.flush()

        account = SourceAccount.query.filter_by(
            provider_key='github', host_key='github.com', native_account_id=account_id
        ).first()
        if account is None:
            account = SourceAccount(
                provider_key='github', host_key='github.com', native_account_id=account_id,
                account_type=observed.account_type,
            )
            db.session.add(account)
            db.session.flush()
        else:
            account.account_type = observed.account_type

        identity = IntegrationInstance(
            integration_type='source_control', provider_key='github', adapter_key='github_rest_v3',
            name=name, environment=str(values.environment or '').strip() or None,
            description=values.description, enabled=bool(values.enabled),
            lifecycle_status='active', readiness_status='validation_required',
            health_status=None,
            metadata_json={
                'provider_label': 'GitHub',
                'protocol': 'github_rest_v3',
                'source_host': 'github.com',
                'auth_type': 'github_app',
                'repository_selection': observed.repository_selection,
            },
        )
        db.session.add(identity)
        db.session.flush()
        installation = SourceInstallation(
            integration_instance_id=identity.id, provider_key='github',
            host_key='github.com', native_app_id=app_id, native_installation_id=installation_id,
            account_id=account.id, github_app_credential_id=app_credential.id,
            repository_scope=observed.repository_selection,
            grant_status='unknown', last_observed_at=observed.observed_at,
        )
        db.session.add(installation)
        db.session.commit()
    except (SQLAlchemyError, CredentialEncryptionError):
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise
    return installation
