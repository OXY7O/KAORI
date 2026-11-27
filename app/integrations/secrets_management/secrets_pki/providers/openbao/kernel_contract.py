"""Register the OpenBao implementation alongside the existing Secrets & PKI module."""

from app.integrations.kernel.registry import IntegrationImplementation, IntegrationRegistry
from app.integrations.secrets_management.secrets_pki.providers.openbao.adapter import record_failure, runtime_adapter
from app.integrations.secrets_management.secrets_pki.providers.openbao.service import get_connection, local_provider_enabled
from app.models.openbao import OpenBaoInstance


def _canonical_loader(instance_id: int) -> OpenBaoInstance | None:
    if not local_provider_enabled():
        return None
    return OpenBaoInstance.query.filter_by(integration_instance_id=instance_id).first()


def _record_loader(instance_id: int) -> OpenBaoInstance | None:
    return get_connection(instance_id) if local_provider_enabled() else None


def _detail_url(row: OpenBaoInstance, section: str) -> str:
    return f'/integrations/secrets-management/secrets-pki/openbao/instances/{row.id}#{section}'


def register_implementation(registry: IntegrationRegistry) -> None:
    registry.register_implementation(
        IntegrationImplementation(
            integration_type='secrets_pki',
            provider_key='openbao',
            adapter_key='openbao_http_v1',
            adapter=runtime_adapter,
            instance_loader=_record_loader,
            canonical_record_loader=_canonical_loader,
            record_model=OpenBaoInstance,
            module_path='app.integrations.secrets_management.secrets_pki.providers.openbao',
            detail_url_builder=_detail_url,
            failure_recorder=record_failure,
        )
    )
