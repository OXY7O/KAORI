"""Bounded HV-12 committed Vault Alert Source validation-sample read model."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.secrets_pki.binding_coverage import build_vault_alert_source_sample_summary

AT = datetime(2026, 10, 23, 9, tzinfo=UTC)


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        tables = [IntegrationInstance.__table__, IntegrationBinding.__table__]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        try:
            yield
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _instance(kind='secrets_pki', *, enabled=True, provider=None):
    row = IntegrationInstance(
        integration_type=kind,
        provider_key=provider or ('vault' if kind == 'secrets_pki' else 'alertmanager'),
        adapter_key='test',
        name=f'{kind}-{IntegrationInstance.query.count()}',
        enabled=enabled,
        lifecycle_status='active',
    )
    db.session.add(row)
    db.session.flush()
    return row


def _sample(*, status='qualified', observed=2):
    rows = {
        'observed_rows': observed, 'firing': observed, 'suppressed': 0,
        'unprocessed': 0, 'critical': observed, 'warning': 0, 'info': 0,
    }
    return {
        'status': status,
        'identity_observed': status == 'qualified',
        **({key: None for key in rows} if status != 'qualified' else rows),
    }


def _binding(source, vault, *, status='ready', at=AT, sample=None, key=None, selector=None):
    evidence = sample if sample is not None else _sample()
    row = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id) if key is None else key,
        enabled=True,
        validation_profile='vault-alerts-v1',
        validation_status=status,
        last_validated_at=at,
        selector_json=selector if selector is not None else {
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
        },
        validation_evidence={
            'profile_key': 'vault-alerts-v1',
            'identity_observed': evidence['identity_observed'],
            'vault_alert_sample': evidence,
        },
    )
    db.session.add(row)
    db.session.commit()
    return row


def _result():
    return build_vault_alert_source_sample_summary(now=AT)


def test_no_vault_is_not_healthy_zero(store):
    output = _result()
    assert output['status'] == 'not_configured'
    assert output['observed_rows'] is None


def test_missing_binding_is_not_bound(store):
    _instance()
    db.session.commit()
    assert _result()['status'] == 'not_bound'


def test_qualified_binding_exposes_only_safe_population_counts(store):
    vault, source = _instance(), _instance('alert_source')
    _binding(source, vault)
    output = _result()
    assert output['status'] == 'qualified'
    assert output['observed_rows'] == 2
    assert output['firing'] == 2
    assert output['critical'] == 2
    assert output['last_validated_at'] == AT
    assert not any(key in repr(output).lower() for key in (
        'vault_instance', 'selector', 'fingerprint', 'namespace',
        'secret_path', 'token', 'serial',
    ))


def test_unobserved_sample_retains_unknown_counts(store):
    vault, source = _instance(), _instance('alert_source')
    _binding(source, vault, sample=_sample(status='unobserved'))
    output = _result()
    assert output['status'] == 'unobserved'
    assert output['firing'] is None
    assert output['last_validated_at'] is None


def test_partial_population_never_exposes_other_source_counts(store):
    first, _second, source = _instance(), _instance(), _instance('alert_source')
    _binding(source, first)
    output = _result()
    assert output['status'] == 'partial'
    assert output['observed_rows'] is None


@pytest.mark.parametrize('status,age', [
    ('validation_required', 0),
    ('ready', 25),
    ('blocked', 0),
])
def test_unqualified_binding_does_not_expose_counts(store, status, age):
    vault, source = _instance(), _instance('alert_source')
    _binding(source, vault, status=status, at=AT - timedelta(hours=age))
    assert _result()['status'] == 'needs_validation'
    assert _result()['critical'] is None


@pytest.mark.parametrize('sample', [
    _sample(status='incomplete'),
    {**_sample(), 'firing': 1000},
    {**_sample(), 'critical': -1},
    {**_sample(), 'observed_rows': 101, 'firing': 101, 'critical': 101},
    {**_sample(), 'warning': True},
])
def test_malformed_or_incomplete_sample_is_unknown(store, sample):
    vault, source = _instance(), _instance('alert_source')
    _binding(source, vault, sample=sample)
    assert _result()['status'] == 'needs_validation'
    assert _result()['observed_rows'] is None


def test_wrong_selector_fails_closed(store):
    vault, source = _instance(), _instance('alert_source')
    _binding(source, vault, selector={
        'matchers': [{'label': 'job', 'operator': '=~', 'value': '.*'}],
    })
    assert _result()['status'] == 'needs_validation'


def test_duplicate_active_binding_is_blocked_not_double_counted(store):
    vault, one, two = _instance(), _instance('alert_source'), _instance('alert_source')
    _binding(one, vault)
    _binding(two, vault)
    output = _result()
    assert output['status'] == 'blocked'
    assert output['observed_rows'] is None


def test_disabled_source_is_excluded_from_observed_alert_population(store):
    vault, source = _instance(), _instance('alert_source', enabled=False)
    _binding(source, vault)
    assert _result()['status'] == 'not_bound'


def test_over_budget_vaults_fail_closed(store):
    for _ in range(26):
        _instance()
    db.session.commit()
    output = _result()
    assert output['status'] == 'blocked'
    assert output['firing'] is None


def test_dual_permission_route_never_reads_sample_for_unprivileged_actor(monkeypatch):
    from app.secrets_pki import routes

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only'
    monkeypatch.setattr(
        routes, 'current_user',
        SimpleNamespace(has_permission=lambda permission: permission != 'intelligence.view'),
    )
    monkeypatch.setattr(routes, 'build_secrets_pki_operational_summary', lambda: {})
    monkeypatch.setattr(routes, 'build_vault_binding_coverage', lambda: {})
    monkeypatch.setattr(
        routes, 'build_vault_alert_source_sample_summary',
        lambda: pytest.fail('No Intelligence permission: source sample must never be read'),
    )
    monkeypatch.setattr(routes, 'render_template', lambda _template, **kw: kw)
    with app.test_request_context('/secrets-pki/?tab=signals'):
        result = routes.overview.__wrapped__()
    assert result['alert_source_sample'] is None
    assert result['can_view_intelligence'] is False


def test_authorized_route_projects_safe_sample(monkeypatch):
    from app.secrets_pki import routes

    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-only'
    monkeypatch.setattr(
        routes, 'current_user',
        SimpleNamespace(has_permission=lambda permission: permission in {
            'secrets_pki.view', 'intelligence.view',
        }),
    )
    monkeypatch.setattr(routes, 'build_secrets_pki_operational_summary', lambda: {})
    monkeypatch.setattr(routes, 'build_vault_binding_coverage', lambda: {})
    monkeypatch.setattr(
        routes, 'build_vault_alert_source_sample_summary',
        lambda: {'status': 'qualified', 'observed_rows': 2},
    )
    monkeypatch.setattr(routes, 'render_template', lambda _template, **kw: kw)
    with app.test_request_context('/secrets-pki/?tab=signals'):
        result = routes.overview.__wrapped__()
    assert result['alert_source_sample']['observed_rows'] == 2
    assert result['can_view_intelligence'] is True
