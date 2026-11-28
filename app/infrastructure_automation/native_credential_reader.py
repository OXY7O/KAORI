"""Unwired worker-only native exact-version SSH reader candidate (#5204/#5186).

A provider token and signed deployment receipt are not operation permission.
Only a future independently admitted canonical worker may call the private
adapter after fresh job/actor/remote-grant/trust and mandatory audit checks.
No HTTP route, CLI, Celery task or application caller is provided here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256

from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    ProviderCredentialVersionSelector,
    canonical_statement,
    provider_credential_version_statement,
)
from app.integrations.secrets_management.secrets_pki.providers.issuer_transit import (
    _active_cluster,
    _transport,
    valid_transit_binding,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPTransport, SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.ssh_credential_material import (
    SSHCredentialMaterial,
    qualify_exact_ssh_version,
    qualify_native_ssh_metadata,
)
from app.secrets_pki.issuer_authority import DeploymentAuthority, resolve_deployment_authority

_SEGMENT = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]{0,159}')
_MOUNT = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,159}')
_MAX_TTL = 300


@dataclass(frozen=True, slots=True, repr=False)
class NativeCredentialSelection:
    selector: ProviderCredentialVersionSelector
    deployment: DeploymentAuthority
    # Must be obtained from the locked canonical representation, never a form.
    path: str = field(repr=False)


def _deny() -> SecretProviderError:
    return SecretProviderError('Native exact SSH credential read is unavailable or unqualified.')


def _paths(selection: NativeCredentialSelection) -> tuple[str, str, str]:
    selected, deployment = selection.selector, selection.deployment
    credential = selected.credential
    scope, binding = deployment.scope, deployment.transit
    if (
        not valid_transit_binding(binding)
        or selected.provider_key != scope.provider_key
        or selected.provider_key != binding.provider_key
        or selected.deployment_ref != scope.deployment_ref
        or credential.integration_instance_id != scope.instance_id
        or credential.provider_namespace != scope.provider_namespace
        or credential.provider_namespace != binding.namespace
        or credential.mount != scope.mount
        or _MOUNT.fullmatch(credential.mount) is None
        or not isinstance(selection.path, str)
        or not 1 <= len(selection.path) <= 1024
        or any(_SEGMENT.fullmatch(segment) is None for segment in selection.path.split('/'))
        or sha256(selection.path.encode('utf-8')).hexdigest() != credential.path_sha256
    ):
        raise _deny()
    # Candidate dedicated policy identity, no default or inherited policy.
    policy = 'kaori-ssh-read-' + sha256(canonical_statement({
        'provider': selected.provider_key,
        'deployment_ref': selected.deployment_ref,
        'namespace': credential.provider_namespace,
        'mount': credential.mount,
        'path_sha256': credential.path_sha256,
        'version': credential.version,
    })).hexdigest()
    return f'{credential.mount}/metadata/{selection.path}', f'{credential.mount}/data/{selection.path}', policy


def _current(selection: NativeCredentialSelection, deadline: datetime) -> datetime:
    now = datetime.now(UTC)
    if (
        not isinstance(deadline, datetime)
        or deadline.utcoffset() is None
        or now >= deadline
        or deadline > selection.deployment.expires_at
        or provider_credential_version_statement(
            selection.selector, issued_at=now, expires_at=deadline
        ) is None
        or resolve_deployment_authority(selection.deployment.scope, now=now) != selection.deployment
    ):
        raise _deny()
    return now


def _qualify_token(
    transport: KV2HTTPTransport, token: str, *, policy: str, deadline: datetime,
    metadata_path: str, data_path: str,
) -> None:
    if (
        not isinstance(token, str)
        or not 1 <= len(token) <= 4096
        or not token.isascii()
        or any(not 33 <= ord(char) <= 126 for char in token)
    ):
        raise _deny()
    status, response = transport._request('/v1/auth/token/lookup-self', token=token)
    data = response.get('data')
    remaining = (deadline - datetime.now(UTC)).total_seconds()
    if (
        status != 200
        or not isinstance(data, dict)
        or data.get('policies') != [policy]
        or data.get('identity_policies') not in (None, [])
        or data.get('renewable') is not False
        or type(data.get('ttl')) is not int
        or not 0 < data['ttl'] <= min(_MAX_TTL, remaining)
    ):
        raise _deny()
    code, capabilities = transport._request(
        '/v1/sys/capabilities-self', method='POST', token=token,
        payload={'paths': [metadata_path, data_path]},
    )
    if code != 200:
        raise _deny()
    nested = capabilities.get('data')
    effective = nested if isinstance(nested, dict) else capabilities
    if any(effective.get(path) != ['read'] for path in (metadata_path, data_path)):
        raise _deny()
    if isinstance(nested, dict) and any(
        path in capabilities and capabilities[path] != nested[path] for path in (metadata_path, data_path)
    ):
        raise _deny()


def _read_exact_native_ssh_credential(
    selection: NativeCredentialSelection, *, token: str, deadline: datetime
) -> SSHCredentialMaterial:
    """Private provider transport adapter, deliberately not wired to any task.

    The future worker must establish operation/job admission and a dedicated
    provider-owned ACL first. Policy names and capabilities on two paths do
    not establish global token least privilege. This does not mint/renew a
    token, infer permission from review evidence or try another provider.
    """
    try:
        metadata_path, data_path, policy = _paths(selection)
        _current(selection, deadline)
        root = _transport(selection.deployment.transit, root=True)
        transport = _transport(selection.deployment.transit)
        _active_cluster(root, selection.deployment.transit)
        _qualify_token(transport, token, policy=policy, deadline=deadline,
                       metadata_path=metadata_path, data_path=data_path)
        code, before = transport._request('/v1/' + metadata_path, token=token)
        if code != 200:
            raise _deny()
        qualify_native_ssh_metadata(selection.selector, before)
        _current(selection, deadline)
        # Explicit positive version, never a latest-value fallback.
        code, response = transport._request(
            '/v1/' + data_path, token=token, kv2_version=selection.selector.credential.version
        )
        if code != 200:
            raise _deny()
        code, after = transport._request('/v1/' + metadata_path, token=token)
        if code != 200:
            raise _deny()
        _active_cluster(root, selection.deployment.transit)
        _qualify_token(transport, token, policy=policy, deadline=deadline,
                       metadata_path=metadata_path, data_path=data_path)
        now = _current(selection, deadline)
        return qualify_exact_ssh_version(
            selection.selector, metadata_before=before, data_response=response, metadata_after=after, now=now
        )
    except Exception:
        # No raw request path, token, body or crypto parser error may escape.
        raise _deny() from None
