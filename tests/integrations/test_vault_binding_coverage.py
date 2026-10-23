"""Vault metrics/alerts binding readiness uses committed canonical source evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions.db import db
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.secrets_pki.binding_coverage import build_vault_binding_coverage

AT = datetime(2026, 10, 23, 7, tzinfo=UTC)


@pytest.fixture
def coverage_store():
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


def _instance(*, kind='secrets_pki', provider='vault', enabled=True, lifecycle='active'):
    row = IntegrationInstance(
        integration_type=kind, provider_key=provider, adapter_key='test',
        name=f'{kind}-{provider}-{IntegrationInstance.query.count()}',
        enabled=enabled, lifecycle_status=lifecycle,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _binding(source, vault, *, status='ready', profile='vault-telemetry-v1',
             at=AT, enabled=True, key=None):
    row = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id) if key is None else key,
        binding_role='primary',
        enabled=enabled, validation_profile=profile,
        validation_status=status,
        last_validated_at=at,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_missing_vault_source_cannot_be_a_healthy_zero(coverage_store):
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'not_configured'
    assert posture['alerts']['qualified_vault_sources'] is None


def test_no_binding_is_distinct_from_qualified_alert_or_metrics_coverage(coverage_store):
    _instance()
    db.session.commit()
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'not_bound'
    assert posture['alerts']['status'] == 'not_bound'
    assert posture['metrics']['qualified_vault_sources'] == 0


def test_metrics_and_alert_identity_bindings_qualify_independently(coverage_store):
    vault = _instance()
    metrics = _instance(kind='metrics_source', provider='prometheus')
    alert = _instance(kind='alert_source', provider='alertmanager')
    _binding(metrics, vault)
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'qualified'
    assert posture['alerts']['status'] == 'not_bound'
    _binding(alert, vault, profile='vault-alerts-v1')
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['coverage'] == '1 / 1'
    assert posture['alerts']['status'] == 'qualified'


@pytest.mark.parametrize('status,profile,at', [
    ('validation_required', 'vault-telemetry-v1', AT),
    ('ready', 'wrong-profile', AT),
    ('ready', 'vault-telemetry-v1', AT - timedelta(days=2)),
    ('ready', 'vault-telemetry-v1', AT + timedelta(minutes=1)),
])
def test_unverified_or_stale_metrics_are_not_qualified(coverage_store, status, profile, at):
    vault, metrics = _instance(), _instance(kind='metrics_source')
    _binding(metrics, vault, status=status, profile=profile, at=at)
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'needs_validation'
    assert posture['metrics']['qualified_vault_sources'] == 0


def test_disabled_binding_or_source_does_not_qualify(coverage_store):
    vault = _instance()
    metrics = _instance(kind='metrics_source', enabled=False)
    _binding(metrics, vault)
    assert build_vault_binding_coverage(now=AT)['metrics']['status'] == 'not_bound'
    metrics.enabled = True
    binding = IntegrationBinding.query.one()
    binding.enabled = False
    db.session.commit()
    assert build_vault_binding_coverage(now=AT)['metrics']['status'] == 'not_bound'


def test_foreign_binding_does_not_match_canonical_instance(coverage_store):
    vault = _instance()
    metrics = _instance(kind='metrics_source')
    _binding(metrics, vault, key='999')
    assert build_vault_binding_coverage(now=AT)['metrics']['status'] == 'not_bound'


def test_oversize_vault_fleet_denies_source_counts(coverage_store):
    for _ in range(26):
        _instance()
    db.session.commit()
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'blocked'
    assert posture['metrics']['eligible_vault_sources'] is None


def test_no_secret_paths_or_provider_identity_in_posture(coverage_store):
    vault, metrics = _instance(), _instance(kind='metrics_source')
    _binding(metrics, vault)
    outcome = repr(build_vault_binding_coverage(now=AT))
    assert 'vault_instance' not in outcome
    assert 'provider_key' not in outcome
    assert 'secret_path' not in outcome


def test_template_replaces_static_unbound_claims():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (root / 'app/templates/secrets_pki/overview.html').read_text(encoding='utf-8')
    assert "binding_coverage.metrics.label" in source
    assert "binding_coverage.alerts.label" in source
    assert "Metrics Source Not Bound" not in source
    assert "Alert Evidence Not Bound" not in source


def test_partial_fleet_coverage_is_not_full_qualification(coverage_store):
    first, _second = _instance(), _instance()
    metrics = _instance(kind='metrics_source')
    _binding(metrics, first)
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'partial'
    assert posture['metrics']['coverage'] == '1 / 2'


def test_two_ready_metrics_sources_do_not_count_as_unambiguous_binding(coverage_store):
    vault = _instance()
    first = _instance(kind='metrics_source')
    second = _instance(kind='metrics_source')
    _binding(first, vault)
    _binding(second, vault)
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'needs_validation'
    assert posture['metrics']['qualified_vault_sources'] == 0


def test_excessive_source_bindings_fail_closed(coverage_store):
    vault = _instance()
    for _ in range(101):
        metrics = _instance(kind='metrics_source')
        db.session.add(IntegrationBinding(
            integration_instance_id=metrics.id,
            asset_type='vault_instance',
            asset_key=str(vault.id),
            binding_role='primary',
            enabled=True,
            validation_profile='vault-telemetry-v1',
            validation_status='ready',
            last_validated_at=AT,
        ))
    db.session.commit()
    posture = build_vault_binding_coverage(now=AT)
    assert posture['metrics']['status'] == 'blocked'
    assert posture['metrics']['qualified_vault_sources'] is None
