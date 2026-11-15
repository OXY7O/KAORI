"""Canonical Ansible integration registration, separate from the execution worker."""

from __future__ import annotations

from app.extensions.db import db
from app.integrations.kernel.registry import IntegrationImplementation, IntegrationModule, registry
from app.integrations.orchestration.infrastructure_automation.providers.ansible.adapter import runtime_adapter
from app.models.integration import IntegrationInstance

INTEGRATION_TYPE = 'infrastructure_automation'
PROVIDER_KEY = 'ansible'
ADAPTER_KEY = 'ansible_runner'


def _load(record_id: int) -> IntegrationInstance | None:
    instance = db.session.get(IntegrationInstance, int(record_id))
    if instance is None or instance.integration_type != INTEGRATION_TYPE or instance.provider_key != PROVIDER_KEY:
        return None
    return instance


def _detail_url(instance: IntegrationInstance, section: str) -> str:
    suffix = f'#{section}' if section else ''
    return f'/integrations/orchestration/ansible/instances/{instance.id}{suffix}'


integration_module = IntegrationModule(
    integration_type=INTEGRATION_TYPE,
    label='Infrastructure Automation',
    domain_key='orchestration',
    capability_key='infrastructure_automation',
    icon='workflow',
    description='Governed Git-defined automation source and committed read-only execution evidence.',
    workspace_endpoint='ansible.index',
    module_path='app.integrations.orchestration.infrastructure_automation.providers.ansible',
    worker_queue='automation',
    worker_domain='infrastructure-automation',
    operations=frozenset({'runtime.state', 'host_facts.collect'}),
    operation_queues={'runtime.state': 'inline', 'host_facts.collect': 'automation'},
    capability_keys=('linux.host_facts.localhost',),
    compatibility_profiles=('ansible-localhost-pilot-v1',),
    runtime_label='Infrastructure Automation',
    navigation_endpoint_prefixes=('ansible.',),
)

provider_implementation = IntegrationImplementation(
    integration_type=INTEGRATION_TYPE,
    provider_key=PROVIDER_KEY,
    adapter_key=ADAPTER_KEY,
    adapter=runtime_adapter,
    instance_loader=_load,
    canonical_record_loader=_load,
    module_path='app.integrations.orchestration.infrastructure_automation.providers.ansible',
    detail_url_builder=_detail_url,
)

registry.register(integration_module)
registry.register_implementation(provider_implementation)
