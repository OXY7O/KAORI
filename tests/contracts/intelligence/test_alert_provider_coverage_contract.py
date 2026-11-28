"""Coverage display is not an admission or provider-read capability (#5230)."""

from app.intelligence.alert_intelligence.provider_case_scope import registered_provider_case_adapters
from app.intelligence.alert_intelligence.provider_coverage import provider_coverage_rows


def test_coverage_tracks_seven_explicit_provider_contracts_without_runtime_claims():
    rows = provider_coverage_rows()
    assert [(row['domain'], row['provider']) for row in rows] == [
        ('Kubernetes', 'Kubernetes'),
        ('Object Storage', 'MinIO'),
        ('Artifact Registry', 'Harbor'),
        ('Secrets & PKI', 'Vault'),
        ('Secrets & PKI', 'OpenBao'),
        ('Source Control', 'GitHub'),
        ('Infrastructure Automation', 'Ansible'),
    ]
    assert [row['origin'] for row in rows] == [
        'Recommendation', 'Recommendation', 'Recommendation', 'Provider alert',
        'Not admitted', 'Not admitted', 'Not admitted',
    ]
    assert all('available' not in row['status'].lower() for row in rows)
    assert all(set(row) == {'domain', 'provider', 'origin', 'status', 'tone', 'limitation'} for row in rows)


def test_only_registered_vault_adapter_is_described_as_scoped_read():
    registered = registered_provider_case_adapters()
    assert registered == frozenset({('secrets_pki', 'vault')})
    rows = provider_coverage_rows()
    assert [row['provider'] for row in rows if row['status'] == 'Scoped read registered'] == ['Vault']
    assert all(row['status'] == 'Not qualified' for row in rows[4:])


def test_coverage_output_cannot_mutate_authoritative_registry():
    first = provider_coverage_rows()
    first[3]['status'] = 'Qualified in production'
    assert provider_coverage_rows()[3]['status'] == 'Scoped read registered'


def test_coverage_is_on_demand_in_shared_overview_not_inline_panels():
    from pathlib import Path

    root = Path('app/templates/intelligence/partials')
    include = "include 'intelligence/partials/_alert_provider_coverage.html'"
    page = (root / '_alert_intelligence_page.html').read_text(encoding='utf-8')
    workspace = (root / '_alert_intelligence_workspace.html').read_text(encoding='utf-8')
    assert page.count(include) == 1
    assert "payload.tab == 'overview'" in page
    overview = (root / '_alert_ops_overview.html').read_text(encoding='utf-8')
    provider = (root / '_vault_provider_case_overview.html').read_text(encoding='utf-8')
    actions = (root.parent / 'components' / '_alert_readiness_actions.html').read_text(encoding='utf-8')
    guide = workspace.split('{% set workspace_guide %}', 1)[1].split('{% endset %}', 1)[0]
    assert 'coverage_button' not in guide
    assert 'data-alert-readiness-actions' in overview
    assert 'readiness_ui.readiness_actions()' in overview
    assert 'readiness_ui.coverage_button()' in provider
    assert 'readiness_ui.coverage_button()' in workspace
    assert actions.count("table_ui.action_classes(size='header')") == 3
    assert 'Quick Actions' in actions
    assert 'grid grid-cols-1 gap-2' in actions
    assert 'flex-wrap' not in actions
    assert 'flex w-full min-w-0 items-center gap-2 text-left' in actions
    assert actions.count("action_classes(size='header') }} w-full") == 2
    assert 'coverage_button(full_width=true)' in actions
    assert 'aria-labelledby="alert-readiness-actions-label"' in actions
    assert 'space-y-2 border-t border-outline-subtle px-4 py-3 sm:px-5' in overview
    assert 'data-dialog-target="alert-provider-coverage-dialog"' in actions
    assert "url_for('notification_channels.index')" in actions
    assert "url_for('platform_operations.data_lifecycle.index', domain='alert_incident')" in actions
    for name in ('_alert_ops_overview.html', '_vault_provider_case_overview.html', '_alert_intelligence_workspace.html'):
        assert include not in (root / name).read_text(encoding='utf-8')
    dialog = (root / '_alert_provider_coverage.html').read_text(encoding='utf-8')
    assert 'data-kaori-native-dialog' in dialog
    assert dialog.count('data-kaori-dialog-close') == 2
    assert 'aria-labelledby="alert-provider-coverage-title"' in dialog
    assert all(f'item.{field}' in dialog for field in ('domain', 'provider', 'origin', 'status', 'tone', 'limitation'))
    assert '<table' not in dialog
