"""SC GitHub capability UI parity with approved KAORI provider workspace (#3297)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.integrations.capability_registry import build_capability_registry_view
from app.integrations.source_control.source_control.providers.github.application.capability_presentation import (
    github_capability_context,
)
from app.integrations.source_control.source_control.providers.github.readiness import _CAPABILITY_PERMISSIONS

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'app/templates/integrations/source_control/github'
ROUTES = ROOT / 'app/integrations/source_control/source_control/providers/github/application/uat_routes.py'


def _canonical(states=None, *, profile='github-app-readiness-v1', validated_at='2026-10-26T08:00:00Z'):
    if states is None:
        return SimpleNamespace(metadata_json={})
    return SimpleNamespace(
        metadata_json={
            'github_validation': {
                'profile': profile,
                'last_validated_at': validated_at,
                'capability_states': states,
            }
        }
    )


def test_unvalidated_installation_does_not_fabricate_ready_or_required_gaps():
    context = github_capability_context(_canonical())
    summary = context['capability_summary']
    assert summary['total'] == len(_CAPABILITY_PERMISSIONS) == 6
    assert summary['verified'] == 0
    assert summary['required_missing'] is None
    assert summary['observed'] is False
    assert all(row['status_key'] == 'unverified' for row in context['capability_rows'])
    assert all(row['status_label'] == 'Not Validated' for row in context['capability_rows'])
    assert not any(row['available'] for row in context['capability_rows'])
    registry = build_capability_registry_view(
        context['capability_rows'],
        distinguish_optional_gap=True,
        distinguish_unverified=True,
    )
    assert len(registry['rows']) == 5
    assert registry['pagination']['total_items'] == 6
    for status, expected in [('blocked', 0), ('unverified', 5)]:
        result = build_capability_registry_view(
            context['capability_rows'],
            status=status,
            distinguish_optional_gap=True,
            distinguish_unverified=True,
        )
        assert len(result['rows']) == expected


def test_committed_capabilities_do_not_imply_repository_inventory_sync():
    states = {
        'repository_inventory': 'permission_verified',
        'source_revision': 'permission_verified',
        'pull_requests': 'permission_unavailable',
        'workflow_runs': 'permission_verified',
        'check_runs': 'permission_unavailable',
        'deployments': 'permission_unavailable',
    }
    rows = github_capability_context(_canonical(states))
    summary = rows['capability_summary']
    assert summary['observed'] is True
    assert summary['verified'] == 3
    assert summary['required_missing'] == 0
    assert summary['optional_verified'] == 1
    assert {row['key'] for row in rows['capability_rows'] if row['available']} == {
        'repository_inventory',
        'source_revision',
        'workflow_runs',
    }
    assert all('permission' in row['probe'].lower() for row in rows['capability_rows'])
    assert all('synchroniz' not in row['evidence'].lower() for row in rows['capability_rows'])
    assert all('required' in row and 'status_key' in row for row in rows['capability_rows'])
    view = build_capability_registry_view(
        rows['capability_rows'],
        requirement='optional',
        status='optional_gap',
        per_page=5,
        distinguish_optional_gap=True,
        distinguish_unverified=True,
    )
    assert len(view['rows']) == 3
    assert all(not row['required'] and not row['available'] for row in view['rows'])


def test_partial_and_unknown_capability_states_cannot_become_verified():
    rows = github_capability_context(_canonical({'repository_inventory': 'permission_verified'}))
    assert rows['capability_summary']['required_missing'] == 1
    assert rows['capability_summary']['verified'] == 1
    assert next(row for row in rows['capability_rows'] if row['key'] == 'source_revision')['available'] is False
    stale = github_capability_context(_canonical({'source_revision': 'permission_verified'}, profile='invalid-profile'))
    assert stale['capability_summary']['observed'] is False
    assert stale['capability_summary']['verified'] == 0
    missing_timestamp = github_capability_context(
        _canonical({'source_revision': 'permission_verified'}, validated_at='')
    )
    assert missing_timestamp['capability_summary']['observed'] is False


def test_github_validation_reuses_provider_readiness_registry_and_detail_components():
    detail = (TEMPLATES / 'uat_detail.html').read_text()
    validation = (TEMPLATES / 'partials/_detail_validation.html').read_text()
    inventory = (TEMPLATES / 'partials/_detail_inventory.html').read_text()
    registry = (TEMPLATES / 'partials/_capability_registry.html').read_text()
    routes = ROUTES.read_text()
    shared_readiness = (ROOT / 'app/templates/integrations/components/_capability_readiness.html').read_text()
    for token in (
        'components/connection_validation_header.html',
        'integrations/components/_capability_readiness.html',
        'integrations/components/_readiness_explanation.html',
        'capability_readiness.render(',
        'readiness_explanation.render(',
        'data-kaori-provider-capability-matrix',
        'Run Full Validation',
        'action_form.hidden_tag()',
        'integrations/components/_validation_poller.html',
        'integrations/components/_provider_job_status.html',
        'framed_workspace_tabs.badge_oob(',
        'hx-post="{{ url_for(\'github_source_uat.validate\', installation_id=installation.id) }}"',
        'hx-indicator="#github-validation-loading"',
    ):
        assert token in validation
    for token in (
        'data-kaori-server-filtered-registry',
        'data-kaori-capability-table-standard',
        'components/pagination.html',
        'components/loading_bar.html',
        'integrations/components/_record_detail_modal.html',
        'integrations/components/_provider_capability_detail.html',
        'integrations/components/_record_actions.html',
        'provider_capability_detail.content(',
        'record_actions.view_more(',
        'table-fixed',
        'Not Validated',
        'View More',
        'hx-indicator="#{{ loading_id }}"',
    ):
        assert token in registry
    assert 'partials/_detail_validation.html' in detail
    assert 'data-kaori-capability-readiness' in shared_readiness
    assert "requested_tab = request.args.get('tab', '')" in detail
    assert 'def _capability_context(canonical)' in routes
    assert 'def capability_registry(installation_id: int)' in routes
    assert "@permission_required('integrations.manage')\ndef capability_registry(" in routes
    assert 'installation = _installation_or_404(installation_id)' in routes
    assert 'build_capability_registry_view(' in routes
    assert 'distinguish_unverified=True' in routes
    assert "url_for('github_source_uat.validate', installation_id=installation.id)" in validation
    assert 'def _validation_job_for(canonical, *, operation:' in routes
    assert 'get_active_validation_task_id(' in routes
    assert 'def validation_status(installation_id: int, task_id: str)' in routes
    assert 'validate_snapshot_access(' in routes
    assert 'validation_poll_response(' in routes
    assert 'integration_instance_id=installation.integration_instance_id' in routes
    assert "url_for('github_source_uat.synchronize', installation_id=installation.id)" in inventory
    assert 'provider_key' not in registry
    assert 'credential.private_key_pem' not in registry
    assert '<style' not in validation and '<script' not in validation


def test_registry_filters_search_pagination_and_unknown_status():
    rows = github_capability_context(_canonical())['capability_rows']
    result = build_capability_registry_view(
        rows,
        query='pull',
        page=1,
        per_page=5,
        search_fields=('label', 'category', 'description'),
        distinguish_optional_gap=True,
        distinguish_unverified=True,
    )
    assert result['pagination']['total_items'] == 1
    assert result['rows'][0]['key'] == 'pull_requests'
    assert (
        build_capability_registry_view(
            rows,
            status='ready',
            distinguish_unverified=True,
        )['rows']
        == []
    )


def test_github_capability_modal_preserves_unverified_semantics():
    shared = (ROOT / 'app/templates/integrations/components/_provider_capability_detail.html').read_text()
    registry = (TEMPLATES / 'partials/_capability_registry.html').read_text()
    assert "row.status_key == 'unverified'" in shared
    assert 'row.status_key == "unverified"' in registry
    assert 'integration_status(tone, row.status_label, display="indicator")' in registry
    assert "status_key = 'unverified'" not in registry
