"""HV-12 source-owned, short-lived Vault correlation evidence has no case side effects."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.extensions.db import db
from app.intelligence.alert_signals.vault_source import (
    SIGNAL_KEY,
    commit_vault_alert_observations,
    read_vault_alert_observations,
)
from app.models.alert_signal import AlertSignalSnapshot
from app.models.integration import IntegrationBinding, IntegrationInstance

AT = datetime(2026, 10, 23, 2, tzinfo=UTC)
KEY = b'TEST-ONLY-correlation-key-with-32-bytes-DO-NOT-USE'


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only', SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            IntegrationInstance.__table__,
            IntegrationBinding.__table__,
            AlertSignalSnapshot.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        try:
            yield
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _instance(kind, provider):
    row = IntegrationInstance(
        integration_type=kind, provider_key=provider, adapter_key='test',
        name=f'{kind}-{IntegrationInstance.query.count()}',
        enabled=True, lifecycle_status='active',
    )
    db.session.add(row)
    db.session.flush()
    return row


def _scoped_binding(vault, source):
    row = IntegrationBinding(
        integration_instance_id=source.id,
        asset_type='vault_instance', asset_key=str(vault.id), enabled=True,
        validation_profile='vault-alerts-v1', validation_status='ready',
        last_validated_at=AT,
        selector_json={
            'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
        },
        validation_evidence={
            'profile_key': 'vault-alerts-v1',
            'vault_alert_sample': {'status': 'qualified'},
        },
    )
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture
def accepted_source(store):
    vault = _instance('secrets_pki', 'vault')
    source = _instance('alert_source', 'alertmanager')
    binding = _scoped_binding(vault, source)
    return vault, source, binding


def _alert(vault_id, *, state='active', severity='warning', fingerprint='aabbccddeeff1234',
           starts='2026-10-23T01:00:00Z'):
    return {
        'labels': {
            'vault_instance': str(vault_id),
            'severity': severity,
            'alertname': 'SECRET-NAME/kv/path-never-store',
        },
        'annotations': {'summary': 'SECRET-NAME/kv/path-never-store'},
        'fingerprint': fingerprint,
        'startsAt': starts,
        'status': {'state': state},
        'generatorURL': 'https://vault.example/secret-value-never-store',
    }


def _commit(binding_id, raw, **kw):
    return commit_vault_alert_observations(
        binding_id=binding_id, alerts=raw, hmac_key=KEY, now=AT, **kw,
    )


def test_qualified_commit_and_read_only_emit_opaque_allowlisted_evidence(accepted_source):
    vault, source, binding = accepted_source
    output = _commit(binding.id, [_alert(vault.id)])
    assert output == {'state': 'qualified', 'observed_rows': 1}
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki', asset_key=str(vault.id), signal_key=SIGNAL_KEY,
    ).one()
    assert snapshot.status == 'ready'
    assert snapshot.payload_json['source_integration_id'] == source.id
    assert snapshot.expires_at is not None
    assert snapshot.generated_at is not None
    result = read_vault_alert_observations(binding_id=binding.id, now=AT)
    assert result['state'] == 'fresh'
    entry = result['entries'][0]
    assert len(entry['handle']) == 64
    assert entry['source_state'] == 'firing'
    assert entry['severity'] == 'warning'
    assert set(entry) == {'handle', 'source_state', 'severity', 'starts_at'}
    committed = repr(snapshot.payload_json)
    for private in ('SECRET-NAME', '/kv/path', 'aabbccddeeff1234',
                    'secret-value-never-store', repr(KEY), 'annotations', 'labels'):
        assert private not in committed
    assert repr(KEY) not in repr(result)


def test_per_alert_handles_are_deterministic_within_same_origin(accepted_source):
    vault, _source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    first = read_vault_alert_observations(binding_id=binding.id, now=AT)['entries'][0]['handle']
    output = commit_vault_alert_observations(
        binding_id=binding.id, alerts=[_alert(vault.id)], hmac_key=KEY,
        now=AT + timedelta(minutes=1),
    )
    assert output['state'] == 'qualified'
    second = read_vault_alert_observations(
        binding_id=binding.id, now=AT + timedelta(minutes=1),
    )['entries'][0]['handle']
    assert first == second


def test_replayed_observation_never_overwrites_newer_snapshot(accepted_source):
    vault, _source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    result = _commit(binding.id, [], observed_at=AT)
    assert result['state'] == 'replayed'
    fresh = read_vault_alert_observations(binding_id=binding.id, now=AT)
    assert fresh['state'] == 'fresh'
    assert len(fresh['entries']) == 1


def test_empty_provider_sample_is_unobserved_not_recovery(accepted_source):
    _vault, _source, binding = accepted_source
    assert _commit(binding.id, [])['state'] == 'unobserved'
    assert read_vault_alert_observations(binding_id=binding.id, now=AT) == {
        'state': 'unobserved', 'entries': None,
    }


@pytest.mark.parametrize('modify', [
    lambda alert: {**alert, 'labels': {**alert['labels'], 'vault_instance': '999'}},
    lambda alert: {**alert, 'labels': {**alert['labels'], 'severity': 'raw-sensitive'}},
    lambda alert: {**alert, 'status': {'state': 'resolved'}},
    lambda alert: {**alert, 'fingerprint': 'SECRET-PATH'},
    lambda alert: {**alert, 'startsAt': '2026-10-23T01:00:00'},
    lambda alert: {**alert, 'startsAt': '2026-10-23T04:00:00Z'},
    lambda alert: {**alert, 'startsAt': 'malformed-source'},
])
def test_unsafe_alert_rows_fail_closed_and_discard_payload(accepted_source, modify):
    vault, _source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    result = commit_vault_alert_observations(
        binding_id=binding.id,
        alerts=[modify(_alert(vault.id))],
        hmac_key=KEY,
        now=AT + timedelta(minutes=1),
    )
    assert result['state'] == 'blocked'
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki', asset_key=str(vault.id), signal_key=SIGNAL_KEY,
    ).one()
    assert snapshot.status == 'failed'
    assert snapshot.payload_json is None
    assert 'SECRET' not in str(snapshot.last_error)
    assert read_vault_alert_observations(
        binding_id=binding.id, now=AT + timedelta(minutes=1),
    )['state'] == 'unavailable'


def test_duplicated_occurrence_and_high_cardinality_are_rejected(accepted_source):
    vault, _source, binding = accepted_source
    alert = _alert(vault.id)
    assert _commit(binding.id, [alert, alert])['state'] == 'blocked'
    assert commit_vault_alert_observations(
        binding_id=binding.id, alerts=[alert] * 101, hmac_key=KEY,
        now=AT + timedelta(minutes=1),
    )['state'] == 'blocked'


def test_disabled_or_ambiguous_source_fails_closed(accepted_source):
    vault, source, binding = accepted_source
    source.enabled = False
    db.session.commit()
    assert _commit(binding.id, [_alert(vault.id)])['state'] == 'blocked'
    source.enabled = True
    other_source = _instance('alert_source', 'alertmanager')
    _scoped_binding(vault, other_source)
    assert _commit(binding.id, [_alert(vault.id)])['state'] == 'blocked'


def test_wrong_selector_or_stale_validation_does_not_commit(accepted_source):
    vault, _source, binding = accepted_source
    binding.selector_json = {
        'matchers': [{'label': 'job', 'operator': '=~', 'value': '.*'}],
    }
    db.session.commit()
    assert _commit(binding.id, [_alert(vault.id)])['state'] == 'blocked'
    binding.selector_json = {
        'matchers': [{'label': 'vault_instance', 'operator': '=', 'value': str(vault.id)}],
    }
    binding.last_validated_at = AT - timedelta(days=2)
    db.session.commit()
    assert _commit(binding.id, [_alert(vault.id)])['state'] == 'blocked'


def test_missing_key_or_untrusted_timestamp_cannot_write(accepted_source):
    vault, _source, binding = accepted_source
    with pytest.raises(ValueError, match='correlation key'):
        commit_vault_alert_observations(
            binding_id=binding.id, alerts=[_alert(vault.id)], hmac_key=b'weak', now=AT,
        )
    with pytest.raises(ValueError, match='timezone-aware'):
        commit_vault_alert_observations(
            binding_id=binding.id, alerts=[_alert(vault.id)], hmac_key=KEY,
            now=AT, observed_at=AT.replace(tzinfo=None),
        )
    assert AlertSignalSnapshot.query.count() == 0


def test_stale_snapshot_and_disabled_vault_are_unknown(accepted_source):
    vault, _source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    assert read_vault_alert_observations(
        binding_id=binding.id, now=AT + timedelta(minutes=6),
    ) == {'state': 'stale', 'entries': None}
    vault.enabled = False
    db.session.commit()
    assert read_vault_alert_observations(
        binding_id=binding.id, now=AT,
    ) == {'state': 'unavailable', 'entries': None}


def test_tampered_committed_evidence_never_becomes_qualified(accepted_source):
    vault, _source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki', asset_key=str(vault.id), signal_key=SIGNAL_KEY,
    ).one()
    altered = dict(snapshot.payload_json)
    altered['entries'] = [{
        'handle': 'x' * 64,
        'severity': 'warning',
        'source_state': 'firing',
        'starts_at': '2026-10-23T01:00:00+00:00',
    }]
    snapshot.payload_json = altered
    db.session.commit()
    assert read_vault_alert_observations(binding_id=binding.id, now=AT)['state'] == 'unavailable'


def test_no_alertcase_or_notification_side_effects_exist_in_source_module():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / 'app/intelligence/alert_signals/vault_source.py'
    code = path.read_text(encoding='utf-8')
    assert 'AlertCase.query' not in code
    assert 'AlertRoutingPolicy' not in code
    assert 'send_channel' not in code
    assert 'get_alerts(' not in code


def test_identical_upstream_fingerprint_cannot_correlate_across_vaults(accepted_source):
    first_vault, _source, first_binding = accepted_source
    _commit(first_binding.id, [_alert(first_vault.id)])
    first_handle = read_vault_alert_observations(
        binding_id=first_binding.id, now=AT,
    )['entries'][0]['handle']
    second_vault = _instance('secrets_pki', 'vault')
    second_source = _instance('alert_source', 'alertmanager')
    second_binding = _scoped_binding(second_vault, second_source)
    _commit(second_binding.id, [_alert(second_vault.id)])
    second_handle = read_vault_alert_observations(
        binding_id=second_binding.id, now=AT,
    )['entries'][0]['handle']
    assert first_handle != second_handle


def test_binding_replaced_after_snapshot_cannot_reuse_old_source_identity(accepted_source):
    vault, source, binding = accepted_source
    _commit(binding.id, [_alert(vault.id)])
    source.enabled = False
    new_source = _instance('alert_source', 'alertmanager')
    new_binding = _scoped_binding(vault, new_source)
    assert read_vault_alert_observations(
        binding_id=new_binding.id, now=AT,
    ) == {'state': 'unavailable', 'entries': None}


def test_trusted_payload_failure_does_not_write_fingerprint_on_initial_failure(accepted_source):
    vault, _source, binding = accepted_source
    bad = _alert(vault.id)
    bad['fingerprint'] = 'PRIVATE-PATH-RAW-VALUE'
    outcome = _commit(binding.id, [bad])
    assert outcome['state'] == 'blocked'
    snapshot = AlertSignalSnapshot.query.one()
    assert snapshot.payload_json is None
    assert 'PRIVATE-PATH-RAW-VALUE' not in str(snapshot.last_error)
