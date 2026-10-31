"""Canonical GitHub installation eligibility used by admission and worker revalidation."""

from __future__ import annotations

from app.models.source_control import SourceInstallation

MAX_INSTALLATIONS = 25


def _eligible(installation: SourceInstallation) -> bool:
    identity = installation.integration_instance
    app = installation.github_app_credential
    account = installation.account
    return bool(
        identity is not None
        and identity.id == installation.integration_instance_id
        and identity.integration_type == 'source_control'
        and identity.provider_key == 'github'
        and identity.adapter_key == 'github_rest_v3'
        and identity.enabled
        and identity.lifecycle_status == 'active'
        and identity.readiness_status == 'ready'
        and installation.provider_key == 'github'
        and installation.host_key == 'github.com'
        and installation.repository_scope in {'all', 'selected'}
        and account is not None
        and account.provider_key == 'github'
        and account.host_key == installation.host_key
        and installation.account_id == account.id
        and app is not None
        and app.enabled
        and app.host_key == installation.host_key
        and app.native_app_id == installation.native_app_id
        and installation.github_app_credential_id == app.id
    )
