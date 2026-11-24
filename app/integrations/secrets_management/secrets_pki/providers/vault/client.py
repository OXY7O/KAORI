"""HashiCorp Vault client with its existing provider-specific trust policy."""

from app.integrations.secrets_management.secrets_pki.providers.kv2_http import KV2HTTPClient
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError as VaultProviderError


class VaultClient(KV2HTTPClient):
    provider_label = 'Vault'
    allowed_origins_env = 'INTEGRATION_VAULT_ALLOWED_ORIGINS'
    ca_bundle_env = 'INTEGRATION_VAULT_CA_BUNDLE'
