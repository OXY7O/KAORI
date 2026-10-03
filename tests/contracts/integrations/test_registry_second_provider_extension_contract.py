from app.integrations.kernel.registry import (
    IntegrationImplementation,
    IntegrationRegistry,
    get_integration,
)


class _SyntheticRegistryAdapter:
    integration_type = 'registry'

    def execute(self, operation, instance, **kwargs):
        return {'operation': operation, 'instance': instance, **kwargs}

    def get_state(self, instance, *, validation_result=None):
        return {'instance': instance, 'validation_result': validation_result}


def test_second_registry_provider_registers_without_harbor_code_changes() -> None:
    local = IntegrationRegistry()
    local.register(get_integration('registry'))
    synthetic = IntegrationImplementation(
        integration_type='registry',
        provider_key='aws_ecr',
        adapter_key='aws_ecr_api',
        adapter=_SyntheticRegistryAdapter(),
        instance_loader=lambda _record_id: None,
        canonical_record_loader=lambda _canonical_id: None,
        module_path='tests.synthetic_registry_provider',
    )

    local.register_implementation(synthetic)

    resolved = local.get_implementation('registry', 'aws_ecr')
    assert resolved.provider_key == 'aws_ecr'
    assert resolved.adapter_key == 'aws_ecr_api'
    assert resolved.integration_type == 'registry'
