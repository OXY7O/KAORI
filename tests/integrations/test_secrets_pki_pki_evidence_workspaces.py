"""Public PKI capability pages project only independently qualified aggregate evidence."""

from pathlib import Path

import pytest

from app.secrets_pki import evidence_workspaces as view

ROOT = Path(__file__).resolve().parents[2]


def _validity(status='ready'):
    return {
        'status': status,
        'label': 'Qualified Public X.509' if status == 'ready' else 'No Current Evidence',
        'observed_stored_certificates': 10,
        'within_validity_window': 6,
        'expired': 2,
        'unknown': 1,
        'not_yet_valid': 1,
        'expires_within_7d': 3,
        'expires_8_to_30d': 2,
        'expires_after_30d': 1,
        'last_observed_at': None,
    }


@pytest.fixture
def stub_sources(monkeypatch):
    events = []
    monkeypatch.setattr(view, 'build_stored_pki_validity_posture', lambda: _validity())
    monkeypatch.setattr(
        view,
        'pki_public_readiness',
        lambda: {
            'state': 'committed',
            'label': 'Issuer Committed',
            'approved_mounts': 2,
            'committed_mounts': 2,
            'observed_issuers': 4,
        },
    )
    monkeypatch.setattr(
        view,
        'stored_pki_certificate_readiness',
        lambda: {'state': 'committed', 'label': 'Stored Committed', 'observed_certificates': 10},
    )
    monkeypatch.setattr(
        view,
        'build_certificate_delivery_overlap',
        lambda **kw: events.append(kw) or {'status': 'partial', 'label': 'Partial TLS'},
    )
    return events


def test_certificates_evidence_and_cross_domain_permission(stub_sources):
    denied = view.build_pki_evidence_workspace(
        kind='certificates',
        can_view_kubernetes_tls=False,
    )
    assert denied['delivery'] is None
    assert stub_sources == []
    assert denied['metrics'][0]['value'] == 10
    assert denied['metrics'][2]['value'] == 2

    allowed = view.build_pki_evidence_workspace(
        kind='certificates',
        can_view_kubernetes_tls=True,
    )
    assert allowed['delivery']['status'] == 'partial'
    assert stub_sources == [{'authorized_to_view_kubernetes_tls': True}]


def test_pki_issuer_and_stored_sources_are_separately_qualified(stub_sources, monkeypatch):
    state = view.build_pki_evidence_workspace(kind='pki')
    assert [item['value'] for item in state['metrics']] == [2, 2, 4, 10]
    monkeypatch.setattr(
        view,
        'pki_public_readiness',
        lambda: {'state': 'stale', 'label': 'Partial/Stale', 'observed_issuers': 100},
    )
    other = view.build_pki_evidence_workspace(kind='pki')
    assert all(metric['value'] is None for metric in other['metrics'][:3])
    assert other['metrics'][3]['value'] == 10
    assert other['public']['label'] == 'Partial/Stale'


def test_expiration_windows_are_observed_only_not_leases(stub_sources):
    result = view.build_pki_evidence_workspace(kind='expiration')
    assert [item['value'] for item in result['metrics']] == [2, 3, 2, 1]
    assert result['delivery'] is None and result['public'] is None
    assert 'Lease' in result['description'] or 'rotation' in result['description']


@pytest.mark.parametrize('kind', ['certificates', 'pki', 'expiration'])
def test_stale_validity_never_exposes_zero_or_old_counts(stub_sources, monkeypatch, kind):
    monkeypatch.setattr(view, 'build_stored_pki_validity_posture', lambda: _validity('stale'))
    data = view.build_pki_evidence_workspace(kind=kind)
    if kind != 'pki':
        assert all(item['value'] is None for item in data['metrics'])
    else:
        assert data['metrics'][0]['value'] == 2
        assert data['metrics'][3]['value'] == 10
    assert data['validity']['status'] == 'stale'


def test_unsupported_workspace_is_rejected_before_provider_evidence(stub_sources):
    with pytest.raises(ValueError, match='Unsupported'):
        view.build_pki_evidence_workspace(kind='not-provider-workspace')


def test_workspace_routes_reuse_role_permission_and_violet_shell():
    routes = (ROOT / 'app/secrets_pki/routes.py').read_text(encoding='utf-8')
    html = (ROOT / 'app/templates/secrets_pki/evidence_workspace.html').read_text(
        encoding='utf-8',
    )
    for kind in ('certificates', 'pki', 'expiration'):
        assert f"@secrets_pki_bp.get('/{kind}')" in routes
        marker = f"@secrets_pki_bp.get('/{kind}')"
        excerpt = routes.split(marker, 1)[1][:115]
        assert "@permission_required('secrets_pki.view')" in excerpt
        assert "('secrets_pki.' ~ slug)" not in routes
    assert '{% extends "layouts/app.html" %}' in html
    assert 'components/operational_metric_card.html' in html
    assert 'components/states/_blocked_state.html' in html
    assert "if validity.status == 'ready'" in html
    assert 'if can_view_kubernetes_tls and delivery is not none' in html
    assert 'data-lucide' not in html  # Existing shared primitives own icons.
    for unsafe in (
        'certificate.pem',
        'cert.private_key',
        'item.secret_value',
        'item.path',
        'item.issuer_serial',
        'item.cn',
        'item.san',
    ):
        assert unsafe not in html


def test_existing_operational_four_tab_overview_is_unchanged():
    html = (ROOT / 'app/templates/secrets_pki/overview.html').read_text(encoding='utf-8')
    assert 'operational_dashboard_workspace.html' in html
    assert "'secrets-pki-overview'" in html
