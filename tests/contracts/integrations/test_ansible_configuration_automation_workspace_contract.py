"""Issue #4834: canonical Ansible registration workspace, not a worker dashboard."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app import create_app
from app.common.pagination import build_pagination_window, pagination_payload
from app.integrations.orchestration.configuration_automation import frontpage, integration_module
from app.integrations.orchestration.configuration_automation.providers.ansible import provider_implementation
from app.integrations.orchestration.configuration_automation.providers.ansible.service import source_validation_posture
from app.integrations.provider_matrix import provider_kind
from app.integrations.taxonomy import get_capability_definition

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = 'integrations/orchestration/configuration_automation/providers/ansible/frontpage.html'
PARTIAL = 'integrations/orchestration/configuration_automation/providers/ansible/_connection_registry.html'
DETAIL = 'integrations/orchestration/configuration_automation/providers/ansible/detail.html'


def _empty_context(monkeypatch):
    def empty_registry(**kwargs):
        return (
            [],
            pagination_payload(
                build_pagination_window(total_items=0, page=kwargs['page'], per_page=kwargs['per_page'])
            ),
            {'total': 0, 'ready': 0, 'attention': 0},
        )

    monkeypatch.setattr(frontpage, 'list_connections', empty_registry)
    return frontpage.build_ansible_frontpage(page=100, per_page=700)


def test_an_ansible_provider_is_registration_available_but_not_runnable() -> None:
    capability = get_capability_definition('orchestration', 'configuration_automation')
    kind = provider_kind('configuration_automation', 'ansible')
    assert capability.label == 'Configuration Automation'
    assert kind.available
    assert kind.adapter_key == 'ansible_runner'
    assert integration_module.workspace_endpoint == 'integrations.ansible'
    assert integration_module.operations == frozenset()
    assert provider_implementation.adapter.integration_type == 'configuration_automation'


def test_empty_registry_clamps_pagination_and_never_claims_readiness(monkeypatch) -> None:
    context = _empty_context(monkeypatch)
    assert context['pagination']['per_page'] == 5
    assert context['pagination']['page'] == 1
    assert context['stats'] == {'total': 0, 'ready': 0, 'attention': 0}
    assert not context['rows']


def test_frontpage_choose_form_and_four_tab_detail_render_with_violet_components(monkeypatch) -> None:
    _empty_context(monkeypatch)
    app = create_app('testing')
    app.config['WTF_CSRF_ENABLED'] = False
    principal = SimpleNamespace(
        id=None,
        is_authenticated=False,
        username='ui-test',
        role_name='Viewer',
        has_permission=lambda _: False,
    )
    monkeypatch.setattr('flask_login.utils._get_user', lambda: principal)
    from app.integrations.orchestration.configuration_automation.providers.ansible.forms import (
        AnsibleSourceConnectionForm,
    )

    with app.test_request_context('/integrations/ansible'):
        context = frontpage.build_ansible_frontpage()
        full = render_template(TEMPLATE, **context)
        partial = render_template(PARTIAL, **context)
        choose = render_template('integrations/orchestration/configuration_automation/providers/ansible/choose.html')
        form = render_template(
            'integrations/orchestration/configuration_automation/providers/ansible/form.html',
            form=AnsibleSourceConnectionForm(),
            source_test_proof='',
            feedback=None,
            feedback_tone='warning',
        )
        connection = SimpleNamespace(
            id=1,
            name='Kubespray Lab',
            environment='laboratory',
            description=None,
            metadata_json={
                'profile_key': 'kubernetes_lifecycle',
                'source_repository': 'OXY7O/kaori-operations',
                'source_sha': 'a' * 40,
                'ansible_core_version': '2.19.3',
                'ansible_runner_version': '2.4.3',
                'kubespray_release': 'v2.32.0',
                'source_validation': {'status': 'source_checked', 'checked_files': 5},
            },
        )
    # A detail page requires a path-bound canonical instance ID for the
    # shared pagination component to construct its full/HTMX navigation URLs.
    with app.test_request_context('/integrations/ansible/connections/1'):
        detail = render_template(
            DETAIL,
            connection=connection,
            source=connection.metadata_json,
            source_posture=source_validation_posture(connection),
            inventory_targets=[],
            inventory_pagination=pagination_payload(build_pagination_window(total_items=0)),
            jobs=[],
            pagination=pagination_payload(build_pagination_window(total_items=0)),
        )
    assert 'data-kaori-ansible-workspace' in full
    assert 'Connection Registry' in full
    assert 'No Ansible Connections' in full
    assert 'data-kaori-ansible-connection-registry' in partial
    assert 'data-kaori-canonical-registry-filter' in partial
    assert 'data-kaori-canonical-registry-footer' in partial
    assert 'Choose Automation Profile' in choose
    assert 'Kubernetes Lifecycle' in choose
    assert 'Linux Host Management' in choose
    assert 'Validate Source' in form
    assert 'Test Connection' not in form  # Shared Hero shows this provider's real pre-save action.
    assert 'source_test_proof' in form
    assert 'grid gap-6 xl:grid-cols-12 xl:items-start' in form
    assert 'min-w-0 xl:col-span-8' in form
    assert 'min-w-0 space-y-4 xl:col-span-4 xl:sticky xl:top-5' in form
    assert 'Kubernetes Source Registration' in form
    assert 'Source Validation Gates' in form
    assert 'id="ansible-identity-heading"' in form
    assert 'id="ansible-source-heading"' in form
    assert 'id="ansible-compatibility-heading"' in form
    assert 'x-on:input.capture="invalidate($event)"' in form
    assert 'x-on:change.capture="invalidate($event)"' in form
    assert 'name="action"' in form
    assert 'value="test"' in form
    assert 'value="save"' in form
    assert 'Ansible Connection Actions' in form
    assert form.index('id="ansible-identity-heading"') < form.index('id="ansible-source-heading"')
    assert form.index('id="ansible-source-heading"') < form.index('id="ansible-compatibility-heading"')
    for name in (
        'Configuration',
        'Validation &amp; Capabilities',
        'Runtime &amp; History',
        'Inventory &amp; Lifecycle',
    ):
        assert name in detail
    assert 'No committed execution history' in detail
    assert 'No infrastructure mutation controls are enabled' in detail


def test_registry_does_not_read_live_runner_or_fabricate_inventory() -> None:
    front = (ROOT / 'app/integrations/orchestration/configuration_automation/frontpage.py').read_text()
    service = (
        ROOT / 'app/integrations/orchestration/configuration_automation/providers/ansible/service.py'
    ).read_text()
    for source in (front, service):
        for banned in ('ansible_runner.run', 'requests.get(', 'subprocess.run', '.apply_async('):
            assert banned not in source
    assert 'integration_instance_id=connection.id' in service
    detail = (ROOT / 'app/templates/' / DETAIL).read_text()
    assert 'framed_workspace_tabs' in detail
    assert 'integrationWorkspaceTabs' in detail
