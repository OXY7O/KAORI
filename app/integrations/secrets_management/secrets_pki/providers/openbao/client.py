"""OpenBao transport for both bundled and external instances (#5201).

Provider registration, ownership, version admission and secret material use
are separate governed boundaries. Never infer provider identity from a
compatible API response or route through another provider's trust policy.
"""

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPClient, KV2HTTPTransport


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
