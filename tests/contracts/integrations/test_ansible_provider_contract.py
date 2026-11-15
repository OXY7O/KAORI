"""Source-owned, database-free Ansible provider and unsafe-input contracts (#4817)."""

from __future__ import annotations

import pytest

from app.infrastructure_automation.source import SOURCE_SHA
from app.integrations.kernel.registry import get_integration, registry
from app.integrations.orchestration.infrastructure_automation.providers.ansible.application.service import (
    AnsibleConnectionForm,
    parse_connection_form,
)
from app.integrations.provider_matrix import provider_kind
from app.models.integration import IntegrationInstance
from app.integrations.taxonomy import get_capability_definition


def test_ansible_is_registered_in_canonical_orchestration_taxonomy() -> None:
    provider = provider_kind('infrastructure_automation', 'ansible')
    assert provider.available is True
    assert provider.domain_key == 'orchestration'
    assert provider.adapter_key == 'ansible_runner'
    assert get_capability_definition('orchestration', 'infrastructure_automation').label == 'Infrastructure Automation'
    module = get_integration('infrastructure_automation')
    assert module.workspace_endpoint == 'ansible.index'
    assert module.queue_for('host_facts.collect') == 'automation'
    assert module.queue_for('runtime.state') == 'inline'
    assert registry.get_implementation('infrastructure_automation', 'ansible').adapter.integration_type == (
        'infrastructure_automation'
    )


def test_registration_accepts_only_safe_identity_fields() -> None:
    parsed = parse_connection_form(
        {'name': '  Lab Ansible ', 'environment': 'uat', 'description': ' Read-only pilot ', 'enabled': 'on'}
    )
    assert parsed == AnsibleConnectionForm(
        name='Lab Ansible', description='Read-only pilot', environment='uat', enabled=True
    )
    assert len(SOURCE_SHA) == 40


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('inventory', 'host=10.0.0.1'),
        ('source_path', '/etc/secrets'),
        ('ssh_private_key', 'should-not-appear-in-a-database'),
        ('playbook', 'cluster.yml'),
        ('become_password', 'sensitive'),
        ('kubeconfig', 'sensitive'),
    ],
)
def test_unsupported_and_sensitive_registration_fields_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValueError, match='Only connection identity'):
        parse_connection_form({'name': 'Lab', 'environment': 'testing', field: value})


@pytest.mark.parametrize(
    'data',
    [
        {'name': '', 'environment': 'uat'},
        {'name': 'x' * 121, 'environment': 'testing'},
        {'name': 'Valid', 'environment': 'production'},
        {'name': 'Valid', 'environment': 'unknown'},
        {'name': 'Valid', 'environment': 'uat', 'description': 'x' * 1001},
    ],
)
def test_unsafe_or_invalid_lifecycle_payload_fails_closed(data: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        parse_connection_form(data)


def test_canonical_only_provider_resolves_detail_without_shadow_record() -> None:
    instance = IntegrationInstance()
    instance.id = 44
    instance.integration_type = 'infrastructure_automation'
    instance.provider_key = 'ansible'
    instance.name = 'Synthetic local worker'
    module = get_integration('infrastructure_automation')
    assert module.detail_url_for_record(instance, section='') == (
        '/integrations/orchestration/ansible/instances/44'
    )
    assert module.implementation_for_record(instance).provider_key == 'ansible'
    instance.integration_type = 'alert_source'
    with pytest.raises(Exception, match='matching canonical integration'):
        module.implementation_for_record(instance)
