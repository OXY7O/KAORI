"""Vault provider AlertCase plan is read-only and never infers source recovery."""

from datetime import UTC, datetime, timedelta

import pytest
from flask import Flask

from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_plan import build_vault_provider_case_plan
from app.intelligence.alert_signals.vault_source import commit_vault_alert_observations
from app.models.alert_ops import AlertCase, AlertCaseEvent
from app.models.alert_signal import AlertSignalSnapshot
from app.models.integration import IntegrationBinding, IntegrationInstance

AT = datetime(2026, 10, 23, 5, tzinfo=UTC)
KEY = b'fixture-only-HMAC-correlation-key-1234567890'


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
        tables = [
            IntegrationInstance.__table__,
            IntegrationBinding.__table__,
            AlertSignalSnapshot.__table__,
            AlertCase.__table__,
            AlertCaseEvent.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        try:
            yield
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _source():
    vault = IntegrationInstance(
        integration_type='secrets_pki',
        provider_key='vault',
        adapter_key='test',
        name='Vault Test',
        enabled=True,
        lifecycle_status='active',
    )
    source = IntegrationInstance(
        integration_type='alert_source',
        provider_key='alertmanager',
        adapter_key='test',
        name='Alertmanager Test',
        enabled=True,
        lifecycle_status='active',
    )
    db.session.add_all([vault, source])
    db.session.flush()
    binding = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance',
        asset_key=str(vault.id),
        enabled=True,
        validation_profile='vault-alerts-v1',
        validation_status='ready',
        selector_json={
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
        },
        validation_evidence={
            'profile_key': 'vault-alerts-v1',
            'vault_alert_sample': {'status': 'qualified'},
        },
        last_validated_at=AT,
    )
    db.session.add(binding)
    db.session.commit()
    return vault, source, binding


def _alert(vault, *, fp='aabbccddeeff1234', state='active', severity='warning'):
    return {
        'labels': {
            'vault_instance': str(vault.id),
            'severity': severity,
            'alertname': 'SECRET/PATH/must-not-appear',
        },
        'annotations': {'summary': 'PRIVATE-KEY-AND-SECRET-PATH'},
        'status': {'state': state},
        'fingerprint': fp,
        'startsAt': '2026-10-23T03:00:00Z',
    }


def _commit(binding, alerts, *, now=AT):
    return commit_vault_alert_observations(
        binding_id=binding.id,
        alerts=alerts,
        hmac_key=KEY,
        observed_at=now,
        now=now,
    )


def _plan(binding, *, now=AT):
    return build_vault_provider_case_plan(binding_id=binding.id, now=now)


def _case(vault, source, binding, case_key, *, closed=False, **updates):
    case = AlertCase(
        case_key=case_key,
        source_type='provider_alert',
        source_ref=case_key,
        domain='secrets_pki',
        asset_type='vault_instance',
        asset_key=str(vault.id),
        asset_name='Approved Vault',
        alert_name='Sanitized Vault source alert',
        severity='warning',
        source_state='firing',
        workflow_state='closed' if closed else 'open',
        routing_state='suppressed',
        routing_override_reason='policy_ineligible',
        labels_json={},
        evidence_json={
            'correlation_profile': 'vault-alert-hmac-v1',
            'source_binding_id': binding.id,
            'source_integration_id': source.id,
        },
    )
    for name, value in updates.items():
        setattr(case, name, value)
    db.session.add(case)
    db.session.commit()
    return case


def test_first_firing_alert_becomes_only_a_create_candidate(store):
    vault, _source_identity, binding = _source()
    assert _commit(binding, [_alert(vault)])['state'] == 'qualified'
    result = _plan(binding)
    assert result['status'] == 'qualified'
    assert result['candidate_count'] == 1
    candidate = result['candidates'][0]
    assert candidate['action'] == 'create_candidate'
    assert candidate['case_key'].startswith('vault-alert:')
    assert len(candidate['case_key']) <= 96
    assert candidate['existing_case_id'] is None
    assert candidate['proposed_routing_state'] == 'suppressed'
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0
    assert not db.session.new
    for secret in ('SECRET/PATH', 'PRIVATE-KEY', 'aabbccddeeff1234', 'annotations', 'labels'):
        assert secret not in repr(result)


def test_repeat_plan_is_deterministic_and_read_only(store):
    vault, _source_identity, binding = _source()
    _commit(binding, [_alert(vault)])
    first, second = _plan(binding), _plan(binding)
    assert first == second
    assert AlertCase.query.count() == 0
    assert AlertCaseEvent.query.count() == 0


def test_existing_identical_open_case_is_refresh_candidate_only(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    existing = _case(vault, source, binding, key)
    result = _plan(binding)
    assert result['candidates'][0]['action'] == 'refresh_candidate'
    assert result['candidates'][0]['existing_case_id'] == existing.id
    assert AlertCase.query.count() == 1
    assert AlertCaseEvent.query.count() == 0


def test_fresh_snapshot_missing_prior_case_never_claims_recovery(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    old_key = _plan(binding)['candidates'][0]['case_key']
    _case(vault, source, binding, old_key)
    _commit(binding, [_alert(vault, fp='0011223344556677')], now=AT + timedelta(minutes=1))
    result = _plan(binding, now=AT + timedelta(minutes=1))
    decisions = {row['case_key']: row['action'] for row in result['candidates']}
    assert decisions[old_key] == 'retain_unverified'
    assert sorted(decisions.values()) == ['create_candidate', 'retain_unverified']
    assert AlertCase.query.one().source_state == 'firing'


@pytest.mark.parametrize('state', ['suppressed', 'unprocessed'])
def test_suppressed_or_unprocessed_source_is_not_new_case_or_recovery(store, state):
    vault, _source_identity, binding = _source()
    _commit(binding, [_alert(vault, state=state)])
    result = _plan(binding)
    assert result['candidates'][0]['action'] == 'review_source'
    assert result['candidates'][0]['observed_source_state'] == state
    assert AlertCase.query.count() == 0


def test_suppressed_source_retains_existing_case_without_resolution(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    _case(vault, source, binding, key)
    _commit(binding, [_alert(vault, state='suppressed')], now=AT + timedelta(minutes=1))
    assert _plan(binding, now=AT + timedelta(minutes=1))['candidates'][0]['action'] == 'retain_unverified'
    assert AlertCase.query.one().source_state == 'firing'


def test_closed_occurrence_is_not_auto_reopened(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    _case(vault, source, binding, key, closed=True)
    assert _plan(binding)['candidates'][0]['action'] == 'review_closed_case'
    assert AlertCase.query.one().workflow_state == 'closed'


def test_same_case_key_in_another_domain_or_asset_blocks_correlations(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    foreign = _case(vault, source, binding, key)
    foreign.domain = 'registry'
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'


def test_duplicate_same_key_and_unknown_case_provenance_blocks(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    _case(vault, source, binding, key)
    second = _case(vault, source, binding, key)
    assert _plan(binding)['status'] == 'blocked'
    db.session.delete(second)
    db.session.commit()
    single = AlertCase.query.one()
    single.evidence_json = {'correlation_profile': 'fake'}
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'


def test_provenance_changed_after_binding_rotation_blocks(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    _case(
        vault,
        source,
        binding,
        key,
        evidence_json={
            'correlation_profile': 'vault-alert-hmac-v1',
            'source_binding_id': binding.id + 100,
            'source_integration_id': source.id,
        },
    )
    assert _plan(binding)['status'] == 'blocked'


@pytest.mark.parametrize('condition', ['unobserved', 'failed', 'expired', 'disabled'])
def test_absent_or_untrustworthy_source_never_resolves_case(store, condition):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    _case(vault, source, binding, key)
    current = AT
    if condition == 'unobserved':
        _commit(binding, [], now=AT + timedelta(minutes=1))
        current = AT + timedelta(minutes=1)
    elif condition == 'failed':
        row = AlertSignalSnapshot.query.one()
        row.status = 'failed'
        row.payload_json = None
        db.session.commit()
    elif condition == 'expired':
        current = AT + timedelta(minutes=6)
    elif condition == 'disabled':
        vault.enabled = False
        db.session.commit()
    result = _plan(binding, now=current)
    assert result['status'] == ('unobserved' if condition == 'unobserved' else 'unavailable')
    assert result['candidates'] is None
    assert AlertCase.query.one().source_state == 'firing'
    assert AlertCaseEvent.query.count() == 0


def test_over_budget_historical_case_population_is_blocked(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    for number in range(101):
        key = f'vault-alert:{number:064x}'
        db.session.add(
            AlertCase(
                case_key=key,
                source_type='provider_alert',
                source_ref=key,
                domain='secrets_pki',
                asset_type='vault_instance',
                asset_key=str(vault.id),
                asset_name='Vault',
                alert_name='Opaque source case',
                routing_state='suppressed',
                evidence_json={
                    'correlation_profile': 'vault-alert-hmac-v1',
                    'source_binding_id': binding.id,
                    'source_integration_id': source.id,
                },
            )
        )
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'
    assert AlertCase.query.count() == 101


def test_qualified_plan_proposes_only_suppressed_routing(store):
    vault, _source_identity, binding = _source()
    _commit(binding, [_alert(vault)])
    item = _plan(binding)['candidates'][0]
    assert item['proposed_routing_state'] == 'suppressed'
    assert 'receiver' not in item
    assert 'notification' not in item
    assert 'owner' not in item


def test_planner_does_not_integrate_with_alertcase_mutation_or_provider_network():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / 'app/intelligence/alert_intelligence/vault_provider_plan.py'
    content = path.read_text(encoding='utf-8')
    assert 'db.session.commit' not in content
    assert 'db.session.add' not in content
    assert 'get_alerts(' not in content
    assert 'mark_case_source_resolved(' not in content
    assert 'mark_case_source_unknown(' not in content
    assert 'create_notification(' not in content


def test_legacy_secret_bearing_case_key_and_unapproved_labels_block(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    canonical = _plan(binding)['candidates'][0]['case_key']
    case = _case(vault, source, binding, canonical)
    case.case_key = 'vault-alert:/v1/secret/legacy-path'
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'
    case.case_key = canonical
    case.labels_json = {'vault_path': 'SECRET/PATH'}
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'


def test_prior_case_with_extra_sensitive_evidence_is_not_reused(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    case = _case(vault, source, binding, key)
    case.evidence_json = {**case.evidence_json, 'raw_provider_annotations': 'PRIVATE/PATH'}
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'


def test_preexisting_provider_case_cannot_be_reenabled_for_routing(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    case = _case(vault, source, binding, key)
    case.routing_state = 'enabled'
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'


def test_policy_ineligible_routing_marker_is_required_for_prior_vault_case(store):
    vault, source, binding = _source()
    _commit(binding, [_alert(vault)])
    key = _plan(binding)['candidates'][0]['case_key']
    case = _case(vault, source, binding, key)
    case.routing_override_reason = 'manual'
    db.session.commit()
    assert _plan(binding)['status'] == 'blocked'
    case.routing_override_reason = 'policy_ineligible'
    db.session.commit()
    assert _plan(binding)['candidates'][0]['action'] == 'refresh_candidate'
