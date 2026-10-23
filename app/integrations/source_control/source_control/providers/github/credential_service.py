"""Credential/installation binding guard for GitHub App probes (#2741).

All provider requests use an existing canonical IntegrationInstance and an
App credential stored encrypted through KAORI's credential boundary.
"""

from __future__ import annotations

from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubAppClient,
    GitHubProviderError,
    InstallationReadiness,
)
from app.models.source_control import SourceInstallation


def build_client_for_installation(installation: SourceInstallation) -> GitHubAppClient:
    canonical = installation.integration_instance
    credential = installation.github_app_credential
    if (
        canonical is None
        or canonical.integration_type != 'source_control'
        or canonical.provider_key != 'github'
        or canonical.adapter_key != 'github_rest_v3'
        or not canonical.enabled
        or canonical.lifecycle_status != 'active'
        or credential is None
        or not credential.enabled
        or installation.provider_key != 'github'
        or installation.host_key != 'github.com'
        or credential.host_key != 'github.com'
        or installation.native_app_id != credential.native_app_id
        or installation.account is None
        or installation.integration_instance_id != canonical.id
    ):
        raise GitHubProviderError('GitHub App connection, installation, or credential is not eligible.')
    return GitHubAppClient(app_id=credential.native_app_id, private_key_pem=credential.private_key_pem)


def probe_installation(installation: SourceInstallation) -> InstallationReadiness:
    """Read-only, bounded validation; never marks the provider Ready on its own."""
    client = build_client_for_installation(installation)
    assert installation.account is not None
    return client.validate_installation(
        installation.native_installation_id, installation.account.native_account_id
    )
