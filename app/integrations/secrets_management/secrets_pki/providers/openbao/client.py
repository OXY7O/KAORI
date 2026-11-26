"""OpenBao transport for both bundled and external instances (#5201).

Provider registration, ownership, version admission and secret material use
are separate governed boundaries. Never infer provider identity from a
compatible API response or route through another provider's trust policy.
"""

import os
from typing import Any

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import (
    KV2HTTPClient,
    KV2HTTPTransport,
    SecretProviderError,
)


class OpenBaoClient(KV2HTTPClient):
    provider_label = 'OpenBao'
    allowed_origins_env = 'INTEGRATION_OPENBAO_ALLOWED_ORIGINS'
    ca_bundle_env = 'INTEGRATION_OPENBAO_CA_BUNDLE'

    @classmethod
    def verify_internal_active_health(cls, *, endpoint: str) -> None:
        """Require the selected release's strict active health without an authentication token."""
        KV2HTTPTransport(
            endpoint=endpoint,
            provider_label=cls.provider_label,
            allowed_origins_env=cls.allowed_origins_env,
            ca_bundle_env=cls.ca_bundle_env,
        ).verify_active_version(expected_version='2.7.3')

    @classmethod
    def inspect_internal_bootstrap(cls, *, endpoint: str, token: str) -> tuple[int, int]:
        """Inspect bounded configuration metadata with transient non-root operator authority."""
        if endpoint != 'https://secret-store:8200' or not os.getenv(cls.ca_bundle_env, '').strip():
            raise SecretProviderError('Internal bootstrap inspection requires the private origin and explicit CA.')
        if not token or not token.isascii() or any(c.isspace() or ord(c) < 33 or ord(c) == 127 for c in token):
            raise SecretProviderError('A valid transient inspection token is required.')
        transport = KV2HTTPTransport(
            endpoint=endpoint,
            provider_label=cls.provider_label,
            allowed_origins_env=cls.allowed_origins_env,
            ca_bundle_env=cls.ca_bundle_env,
        )
        transport.verify_active_version(expected_version='2.7.3')
        _verify_inspection_authority(transport, token)
        _verify_internal_audit(_read_metadata(transport, token, '/v1/sys/audit'))
        mounts = _read_metadata(transport, token, '/v1/sys/mounts')
        auth = _read_metadata(transport, token, '/v1/sys/auth')
        kv2_count = sum(
            1
            for entry in mounts.values()
            if entry.get('type') == 'kv'
            and isinstance(entry.get('options'), dict)
            and entry['options'].get('version') == '2'
        )
        approle_count = sum(1 for entry in auth.values() if entry.get('type') == 'approle')
        return kv2_count, approle_count


def _verify_inspection_authority(transport: KV2HTTPTransport, token: str) -> None:
    status, response = transport._request('/v1/auth/token/lookup-self', token=token)
    data = response.get('data')
    if status != 200 or not isinstance(data, dict):
        raise SecretProviderError('Inspection token authority could not be verified.')
    policies = data.get('policies')
    ttl = data.get('ttl')
    if (
        not isinstance(policies, list)
        or not policies
        or not all(isinstance(policy, str) for policy in policies)
        or 'root' in policies
        or type(ttl) is not int
        or ttl <= 0
    ):
        raise SecretProviderError('Inspection requires a non-root expiring token.')


def _read_metadata(transport: KV2HTTPTransport, token: str, path: str) -> dict[str, Any]:
    code, body = transport._request(path, token=token)
    entries = body.get('data')
    if code != 200 or not isinstance(entries, dict):
        raise SecretProviderError('Required bootstrap metadata could not be verified.')
    if not all(isinstance(entry, dict) for entry in entries.values()):
        raise SecretProviderError('Required bootstrap metadata could not be verified.')
    return entries


def _verify_internal_audit(entries: dict[str, Any]) -> None:
    audit = entries.get('kaori-operator/')
    if not isinstance(audit, dict) or audit.get('type') != 'file':
        raise SecretProviderError('Expected internal file audit configuration is not available.')
    options = audit.get('options')
    if (
        not isinstance(options, dict)
        or options.get('file_path') != '/openbao/audit/audit.jsonl'
        or options.get('log_raw', 'false') != 'false'
    ):
        raise SecretProviderError('Unexpected internal audit configuration.')
