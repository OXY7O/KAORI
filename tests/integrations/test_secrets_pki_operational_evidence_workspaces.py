"""HV-07 safe Lease, Consumer and Governance workspace boundaries."""

from pathlib import Path

import pytest

from app.secrets_pki import operational_evidence_workspaces as domain

ROOT = Path(__file__).resolve().parents[2]


def _version(status='ready'):
    return {
        'status': status,
        'label': 'Committed KV v2 Version Evidence',
        'observed_versions': 8,
        'available': 6,
        'unknown': 2,
    }


@pytest.fixture
def sources(monkeypatch):
    tls_calls = []
    monkeypatch.setattr(domain, 'build_kv2_version_posture', lambda: _version())
    monkeypatch.setattr(
        domain,
        'build_certificate_delivery_overlap',
        lambda **kwargs: (
            tls_calls.append(kwargs)
            or {
                'status': 'overlap_observed',
                'label': 'Same Public Certificate Observed',
                'overlapping_certificates': 3,
                'matching_kubernetes_tls_secrets': 2,
            }
        ),
    )
    monkeypatch.setattr(
        domain,
        'build_secrets_pki_operational_summary',
        lambda: {
            'state': 'committed',
            'label': 'Committed Inventory Evidence',
            'committed_mount_count': 2,
            'observed_secret_count': 7,
        },
    )
    monkeypatch.setattr(
        domain,
        'build_vault_binding_coverage',
        lambda: {
            'metrics': {
                'status': 'qualified',
                'label': 'Metrics Binding Qualified',
                'qualified_vault_sources': 2,
            },
            'alerts': {
                'status': 'needs_validation',
                'label': 'Alert Binding Validation Required',
                'qualified_vault_sources': 0,
            },
        },
    )
    monkeypatch.setattr(
        domain,
        'build_stored_pki_validity_posture',
        lambda: {
            'status': 'ready',
            'label': 'Qualified Public X.509',
            'observed_stored_certificates': 3,
        },
    )
    return tls_calls


def test_leases_never_infers_lease_counts_from_version_metadata(sources):
    view = domain.build_operational_evidence_workspace(kind='leases')
    assert [item['value'] for item in view['metrics']] == [None, None, None, 8]
    assert 'Not Materialized' in view['source_rows'][0]['status']
    assert sources == []


def test_stale_kv2_version_is_not_qualified_lease_evidence(sources, monkeypatch):
    monkeypatch.setattr(domain, 'build_kv2_version_posture', lambda: _version('stale'))
    view = domain.build_operational_evidence_workspace(kind='leases')
    assert all(item['value'] is None for item in view['metrics'])


def test_no_tls_permission_means_no_cross_domain_query(sources):
    view = domain.build_operational_evidence_workspace(
        kind='consumers',
        can_view_kubernetes_tls=False,
    )
    assert sources == []
    assert all(item['value'] is None for item in view['metrics'])
    assert view['source_rows'][1]['status'] == 'Additional TLS Permission Required'


def test_tls_overlap_is_not_confirmed_consumer_or_rotation(sources):
    view = domain.build_operational_evidence_workspace(
        kind='consumers',
        can_view_kubernetes_tls=True,
    )
    assert sources == [{'authorized_to_view_kubernetes_tls': True}]
    assert [item['value'] for item in view['metrics']] == [None, None, 3, 2]
    assert 'not delivery proof' in view['metrics'][2]['description']


def test_partial_tls_evidence_cannot_produce_current_overlap_counts(sources, monkeypatch):
    monkeypatch.setattr(
        domain,
        'build_certificate_delivery_overlap',
        lambda **_kwargs: {
            'status': 'incomplete_evidence',
            'label': 'Stale TLS Overlap',
            'overlapping_certificates': 99,
            'matching_kubernetes_tls_secrets': 22,
        },
    )
    view = domain.build_operational_evidence_workspace(
        kind='consumers',
        can_view_kubernetes_tls=True,
    )
    assert all(item['value'] is None for item in view['metrics'])


def test_governance_qualifies_sources_independently(sources):
    view = domain.build_operational_evidence_workspace(kind='governance')
    assert [item['value'] for item in view['metrics']] == [2, 2, None, 3]
    assert len(view['source_rows']) == 5
    assert sources == []


def test_governance_unknown_never_renders_false_healthy_zero(sources, monkeypatch):
    monkeypatch.setattr(
        domain,
        'build_secrets_pki_operational_summary',
        lambda: {'state': 'partial', 'label': 'Incomplete', 'committed_mount_count': 10},
    )
    monkeypatch.setattr(
        domain,
        'build_vault_binding_coverage',
        lambda: {
            'metrics': {'status': 'partial', 'qualified_vault_sources': 1},
            'alerts': {'status': 'unavailable', 'qualified_vault_sources': 0},
        },
    )
    monkeypatch.setattr(
        domain,
        'build_stored_pki_validity_posture',
        lambda: {'status': 'stale', 'observed_stored_certificates': 3},
    )
    view = domain.build_operational_evidence_workspace(kind='governance')
    assert all(item['value'] is None for item in view['metrics'])


def test_invalid_operational_workspace_has_no_provider_fallback(sources):
    with pytest.raises(ValueError, match='Unknown'):
        domain.build_operational_evidence_workspace(kind='secret-reveal')


def test_all_operational_routes_have_server_side_permissions():
    routes = (ROOT / 'app/secrets_pki/routes.py').read_text(encoding='utf-8')
    for slug in ('leases', 'consumers', 'governance'):
        anchor = f"@secrets_pki_bp.get('/{slug}')"
        assert anchor in routes
        assert "@permission_required('secrets_pki.view')" in routes.split(anchor, 1)[1][:110]
    assert "current_user.has_permission('tls_certificates.view')" in routes


def test_templates_use_violet_shared_components_and_no_sensitive_fields():
    html = (ROOT / 'app/templates/secrets_pki/operational_evidence_workspace.html').read_text(
        encoding='utf-8',
    )
    assert '{% extends "layouts/app.html" %}' in html
    assert 'components/page_hero.html' in html
    assert 'components/operational_metric_card.html' in html
    assert 'components/operational_section_card.html' in html
    assert "metric.value if metric.value is not none else 'Not Qualified'" in html
    assert 'secrets_pki.lifecycle' in html
    for forbidden in (
        'row.path',
        'row.secret_value',
        'lease.provider_id',
        'client_token',
        'private_key',
        'item.namespace',
        'policy.mount',
        'item.case_key',
    ):
        assert forbidden not in html


def test_existing_dashboard_four_tab_controller_preserved():
    html = (ROOT / 'app/templates/secrets_pki/overview.html').read_text(encoding='utf-8')
    assert "dashboard_workspace.controller(active_tab, 'secrets-pki-overview')" in html
