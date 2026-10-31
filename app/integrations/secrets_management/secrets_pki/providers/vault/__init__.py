from datetime import UTC, datetime

from app.integrations.kernel.registry import (
    IntegrationImplementation,
    IntegrationModule,
    canonical_model_loader,
    model_loader,
    registry,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.adapter import runtime_adapter
from app.models.vault import VaultInstance


def _detail_url(instance: VaultInstance, section: str) -> str:
    return f'/integrations/secrets-management/secrets-pki/vault/instances/{instance.id}#{section}'


def _record_failure(instance: VaultInstance, error: Exception) -> None:
    instance.last_checked_at = datetime.now(UTC)
    instance.last_status = 'disconnected'
    instance.last_error = 'Vault API observation failed; review TLS, connectivity and authorization.'
    instance.last_response_time_ms = None


integration_module = IntegrationModule(
    integration_type='secrets_pki',
    label='Secrets & PKI',
    domain_key='secrets_management',
    capability_key='secrets_pki',
    icon='key-round',
    description='Provider-neutral Secrets & PKI connectivity and committed lifecycle evidence.',
    workspace_endpoint='vault.index',
    module_path='app.integrations.secrets_management.secrets_pki.providers.vault',
    worker_queue='integration-runtime',
    worker_domain='secrets-pki-provider',
    operations=frozenset({'connection.test', 'client.build', 'runtime.validate', 'runtime.health', 'runtime.state'}),
    operation_queues={
        'connection.test': 'inline',
        'client.build': 'inline',
        'runtime.validate': 'integration-validation',
        'runtime.health': 'integration-runtime',
        'runtime.state': 'inline',
    },
    capability_keys=('health', 'approle', 'token_lookup', 'mount_metadata'),
    compatibility_profiles=('vault-approle-read-v1',),
    runtime_label='Secrets & PKI',
    navigation_endpoint_prefixes=('vault.',),
)

provider_implementation = IntegrationImplementation(
    integration_type='secrets_pki',
    provider_key='vault',
    adapter_key='vault_http_v1',
    adapter=runtime_adapter,
    instance_loader=model_loader(VaultInstance),
    canonical_record_loader=canonical_model_loader(VaultInstance),
    record_model=VaultInstance,
    module_path='app.integrations.secrets_management.secrets_pki.providers.vault',
    detail_url_builder=_detail_url,
    failure_recorder=_record_failure,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
