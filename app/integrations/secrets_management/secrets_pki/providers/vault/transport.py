"""HashiCorp Vault transport policy over the shared KV v2 HTTPS primitive."""

from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import (
    validate_auth_mount as validate_auth_mount,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_transport import validate_secret_endpoint


def validate_vault_endpoint(value: str) -> str:
    return validate_secret_endpoint(
        value, allowed_origins_env='INTEGRATION_VAULT_ALLOWED_ORIGINS', provider_label='Vault'
    )
