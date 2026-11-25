"""OpenBao transport for both bundled and external instances (#5201).

Provider registration, ownership, version admission and secret material use
are separate governed boundaries. Never infer provider identity from a
compatible API response or route through another provider's trust policy.
"""

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPClient


class OpenBaoClient(KV2HTTPClient):
    provider_label = 'OpenBao'
    allowed_origins_env = 'INTEGRATION_OPENBAO_ALLOWED_ORIGINS'
    ca_bundle_env = 'INTEGRATION_OPENBAO_CA_BUNDLE'
