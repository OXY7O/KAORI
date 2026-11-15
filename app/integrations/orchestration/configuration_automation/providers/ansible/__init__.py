"""Ansible provider: source-only lifecycle and strict fail-closed runtime."""

from app.integrations.kernel.registry import IntegrationImplementation
from app.integrations.orchestration.configuration_automation.providers.ansible.adapter import runtime_adapter
from app.integrations.orchestration.configuration_automation.providers.ansible.service import (
    record_for_canonical,
)


def _detail_url(record, section: str) -> str:
    anchor = f'#{section}' if section else ''
    return f'/integrations/ansible/connections/{record.id}{anchor}'


provider_implementation = IntegrationImplementation(
    integration_type='configuration_automation',
    provider_key='ansible',
    adapter_key='ansible_runner',
    adapter=runtime_adapter,
    instance_loader=record_for_canonical,
    canonical_record_loader=record_for_canonical,
    module_path='app.integrations.orchestration.configuration_automation.providers.ansible',
    detail_url_builder=_detail_url,
)
