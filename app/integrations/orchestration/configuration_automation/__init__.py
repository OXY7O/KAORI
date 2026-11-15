"""Configuration Automation capability: read-only workspace registration only.

The Ansible provider remains planned for real host registration and mutation.
"""
from app.integrations.kernel.registry import IntegrationModule, registry

integration_module = IntegrationModule(
    integration_type='configuration_automation',
    label='Configuration Automation',
    domain_key='orchestration',
    capability_key='configuration_automation',
    icon='workflow',
    description='Git-defined operations, immutable source qualification and canonical execution evidence.',
    workspace_endpoint='integrations.ansible',
    module_path='app.integrations.orchestration.configuration_automation',
    worker_queue='automation',
    worker_domain='orchestration-automation',
    operations=frozenset(),
    operation_queues={},
    runtime_label='Ansible',
    navigation_endpoint_prefixes=('integrations.ansible',),
)

registry.register(integration_module)
