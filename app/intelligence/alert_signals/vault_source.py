"""Vault Alert Source committed observation seam for future canonical AlertCases.

Internal-only API: a trusted worker must supply scoped source rows and an
independently managed HMAC key. No HTTP routes, new engine, provider I/O,
autonomous recovery or automatic AlertCase promotion are enabled here.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from app.extensions.db import db
from app.models.alert_signal import AlertSignalSnapshot
from app.models.integration import IntegrationBinding, IntegrationInstance

SIGNAL_KEY = 'secrets_pki.vault_alertmanager_observations'
_PROFILE = 'vault-alerts-v1'
_TTL = timedelta(minutes=5)
_VALIDATION_AGE = timedelta(hours=24)
_MAX_ALERTS = 100
_FINGERPRINT = re.compile(r'[0-9a-fA-F]{16}\Z')
_HANDLE = re.compile(r'[0-9a-f]{64}\Z')
_STATES = {'active': 'firing', 'suppressed': 'suppressed', 'unprocessed': 'unprocessed'}
_SEVERITIES = frozenset({'critical', 'warning', 'info'})


class _UnsafeSource(ValueError):
    """No source contents may enter the error message."""


def _utc(value: datetime | None) -> datetime | None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(UTC)


def _persisted_utc(value: datetime | None) -> datetime | None:
    """SQLite fixtures may round-trip a UTC timestamp without timezone.

    PostgreSQL preserves timezone in production. Treat legacy/SQLite database
    timestamps as UTC, never do this for untrusted source timestamps.
    """
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _identity(value: object) -> int | None:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        return None
    if not 1 <= len(value) <= 10 or value.startswith('0'):
        return None
    parsed = int(value)
    return parsed if parsed > 0 and str(parsed) == value else None


def _has_exact_vault_matcher(binding: IntegrationBinding) -> bool:
    """Require one exact per-Vault Alert Source matcher."""
    selector = binding.selector_json
    matchers = selector.get('matchers') if isinstance(selector, dict) else None
    return (
        isinstance(matchers, list)
        and len(matchers) == 1
        and matchers[0] == {'label': 'vault_instance', 'operator': '=', 'value': binding.asset_key}
    )


def _validated_binding(binding_id: int, *, now: datetime) -> tuple[IntegrationBinding, IntegrationInstance] | None:
    if type(binding_id) is not int or binding_id < 1:
        return None
    binding = db.session.get(IntegrationBinding, binding_id)
    if (
        binding is None
        or not binding.enabled
        or binding.asset_type != 'vault_instance'
        or binding.validation_status != 'ready'
        or binding.validation_profile != _PROFILE
    ):
        return None
    vault_id = _identity(binding.asset_key)
    if vault_id is None:
        return None
    vault = db.session.get(IntegrationInstance, vault_id)
    source = db.session.get(IntegrationInstance, binding.integration_instance_id)
    if (
        vault is None
        or vault.integration_type != 'secrets_pki'
        or vault.provider_key != 'vault'
        or not vault.enabled
        or vault.lifecycle_status != 'active'
        or source is None
        or source.integration_type != 'alert_source'
        or source.provider_key != 'alertmanager'
        or not source.enabled
        or source.lifecycle_status != 'active'
    ):
        return None
    if not _has_exact_vault_matcher(binding):
        return None
    checked = _persisted_utc(binding.last_validated_at)
    if checked is None or not timedelta(0) <= now - checked <= _VALIDATION_AGE:
        return None
    evidence = binding.validation_evidence
    if not isinstance(evidence, dict) or evidence.get('profile_key') != _PROFILE:
        return None
    sample = evidence.get('vault_alert_sample')
    if (
        not isinstance(sample, dict)
        or not isinstance(sample.get('status'), str)
        or sample['status'] not in {'qualified', 'unobserved'}
    ):
        return None

    # Ambiguous source precedence cannot silently establish per-Vault identity.
    active = (
        db.session.query(IntegrationBinding.id)
        .join(IntegrationInstance, IntegrationInstance.id == IntegrationBinding.integration_instance_id)
        .filter(
            IntegrationBinding.asset_type == 'vault_instance',
            IntegrationBinding.asset_key == binding.asset_key,
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.integration_type == 'alert_source',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .limit(2)
        .all()
    )
    if len(active) != 1 or active[0][0] != binding.id:
        return None
    return binding, source


def _start_at(value: object, *, now: datetime) -> datetime:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise _UnsafeSource('Invalid alert occurrence timestamp.')
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise _UnsafeSource('Invalid alert occurrence timestamp.') from exc
    instant = _utc(stamp)
    if instant is None or instant > now + timedelta(minutes=5):
        raise _UnsafeSource('Invalid alert occurrence timestamp.')
    return instant


def _normalize(
    raw: object,
    *,
    vault_id: str,
    source_id: int,
    hmac_key: bytes,
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(raw, list) or len(raw) > _MAX_ALERTS:
        raise _UnsafeSource('Alert observation safety boundary exceeded.')
    if not raw:
        return {'status': 'unobserved', 'entries': []}
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for alert in raw:
        if not isinstance(alert, dict):
            raise _UnsafeSource('Invalid Alert Source observation.')
        labels = alert.get('labels')
        status = alert.get('status')
        if not isinstance(labels, dict) or labels.get('vault_instance') != vault_id:
            raise _UnsafeSource('Alert Source identity mismatch.')
        state = status.get('state') if isinstance(status, dict) else None
        severity = labels.get('severity')
        fingerprint = alert.get('fingerprint')
        if (
            not isinstance(state, str)
            or state not in _STATES
            or not isinstance(severity, str)
            or severity not in _SEVERITIES
            or not isinstance(fingerprint, str)
            or _FINGERPRINT.fullmatch(fingerprint) is None
        ):
            raise _UnsafeSource('Incomplete Alert Source observation.')
        start = _start_at(alert.get('startsAt'), now=now)
        identity_material = (
            f'vault-alert-v1\0{source_id}\0{vault_id}\0'
            f'{fingerprint.lower()}\0{start.isoformat(timespec="microseconds")}'
        ).encode('ascii')
        handle = hmac.new(hmac_key, identity_material, hashlib.sha256).hexdigest()
        if handle in seen:
            raise _UnsafeSource('Duplicate alert occurrence in source response.')
        seen.add(handle)
        entries.append(
            {
                'handle': handle,
                'source_state': _STATES[state],
                'severity': severity,
                'starts_at': start.isoformat(),
            }
        )
    entries.sort(key=lambda entry: entry['handle'])
    return {'status': 'qualified', 'entries': entries}


def commit_vault_alert_observations(
    *,
    binding_id: int,
    alerts: object,
    hmac_key: bytes,
    observed_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Commit one worker-supplied source snapshot without fetching the provider.

    Passing a payload to this internal API is *not* proof of provider polling
    or UAT. The caller must be a trusted provider-owning JobExecution.
    """
    instant = _utc(now or datetime.now(UTC))
    observed = _utc(observed_at or instant)
    if instant is None or observed is None or not instant - _TTL <= observed <= instant:
        raise ValueError('A recent timezone-aware observation is required.')
    if not isinstance(hmac_key, bytes) or len(hmac_key) < 32:
        raise ValueError('A dedicated non-persisted 32-byte correlation key is required.')
    eligible = _validated_binding(binding_id, now=instant)
    if eligible is None:
        return {'state': 'blocked', 'observed_rows': None}
    binding, source = eligible
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki',
        asset_key=binding.asset_key,
        signal_key=SIGNAL_KEY,
    ).first()
    if snapshot is not None and snapshot.generated_at is not None:
        previous = _persisted_utc(snapshot.generated_at)
        if previous is not None and observed <= previous:
            return {'state': 'replayed', 'observed_rows': None}
    try:
        normalized = _normalize(
            alerts,
            vault_id=binding.asset_key,
            source_id=source.id,
            hmac_key=hmac_key,
            now=observed,
        )
    except _UnsafeSource:
        if snapshot is None:
            snapshot = AlertSignalSnapshot(
                domain='secrets_pki',
                asset_key=binding.asset_key,
                signal_key=SIGNAL_KEY,
            )
            db.session.add(snapshot)
        snapshot.status = 'failed'
        snapshot.payload_json = None
        # Preserve a monotonic generation fence after failed observation.
        snapshot.generated_at = observed
        snapshot.expires_at = None
        snapshot.last_attempt_at = observed
        snapshot.last_error = 'Vault Alert Source evidence rejected by qualification contract.'
        db.session.commit()
        return {'state': 'blocked', 'observed_rows': None}
    if snapshot is None:
        snapshot = AlertSignalSnapshot(
            domain='secrets_pki',
            asset_key=binding.asset_key,
            signal_key=SIGNAL_KEY,
        )
        db.session.add(snapshot)
    snapshot.status = 'ready'
    snapshot.payload_json = {
        'schema_version': 1,
        'source_binding_id': binding.id,
        'source_integration_id': source.id,
        'status': normalized['status'],
        'entries': normalized['entries'],
    }
    snapshot.generated_at = observed
    snapshot.expires_at = observed + _TTL
    snapshot.last_attempt_at = observed
    snapshot.last_error = None
    db.session.commit()
    return {
        'state': normalized['status'],
        'observed_rows': len(normalized['entries']) if normalized['entries'] else None,
    }


def fail_vault_alert_observations(
    *,
    binding_id: int,
    observed_at: datetime | None = None,
) -> bool:
    """Invalidate a previously ready source after a trusted provider read fails.

    A failure only marks committed evidence unavailable. It never resolves
    prior alerts or writes the provider exception/response to persistence.
    """
    instant = _utc(observed_at or datetime.now(UTC))
    if instant is None:
        return False
    eligible = _validated_binding(binding_id, now=instant)
    if eligible is None:
        return False
    binding, _source = eligible
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki',
        asset_key=binding.asset_key,
        signal_key=SIGNAL_KEY,
    ).first()
    if snapshot is None:
        snapshot = AlertSignalSnapshot(
            domain='secrets_pki',
            asset_key=binding.asset_key,
            signal_key=SIGNAL_KEY,
        )
        db.session.add(snapshot)
    previous = _persisted_utc(snapshot.generated_at)
    if previous is not None and instant < previous:
        return False
    snapshot.status = 'failed'
    snapshot.payload_json = None
    snapshot.generated_at = instant
    snapshot.expires_at = None
    snapshot.last_attempt_at = instant
    snapshot.last_error = 'Vault Alert Source observation unavailable.'
    db.session.commit()
    return True



def _qualified_snapshot_payload(
    payload: object, *, binding: IntegrationBinding, source: IntegrationInstance
) -> dict[str, Any] | None:
    """Fail closed unless the stored observation belongs to the exact binding and source."""
    if (
        not isinstance(payload, dict)
        or type(payload.get('schema_version')) is not int
        or payload['schema_version'] != 1
        or type(payload.get('source_binding_id')) is not int
        or payload['source_binding_id'] != binding.id
        or type(payload.get('source_integration_id')) is not int
        or payload['source_integration_id'] != source.id
        or not isinstance(payload.get('status'), str)
        or payload['status'] not in {'qualified', 'unobserved'}
    ):
        return None
    return payload


def _validated_snapshot_alert_handle(entry: object, *, created: datetime, instant: datetime) -> str | None:
    """Validate one committed alert entry without trusting its payload schema."""
    if not isinstance(entry, dict) or set(entry) != {
        'handle',
        'source_state',
        'severity',
        'starts_at',
    }:
        return None
    handle, state, severity, started = (
        entry['handle'],
        entry['source_state'],
        entry['severity'],
        entry['starts_at'],
    )
    if (
        not isinstance(handle, str)
        or _HANDLE.fullmatch(handle) is None
        or not isinstance(state, str)
        or state not in _STATES.values()
        or not isinstance(severity, str)
        or severity not in _SEVERITIES
        or not isinstance(started, str)
        or len(started) > 64
    ):
        return None
    try:
        started_at = _start_at(started, now=created)
    except _UnsafeSource:
        return None
    if started_at > instant + timedelta(minutes=5):
        return None
    return handle


def read_vault_alert_observations(
    *,
    binding_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Internal-only correlation data. User-facing consumers need #724 scope checks.

    An absent, expired, failed or unobserved snapshot is *unknown*, never
    source recovery. Caller must not translate missing entries into resolved.
    """
    instant = _utc(now or datetime.now(UTC))
    if instant is None:
        return {'state': 'unavailable', 'entries': None}
    eligible = _validated_binding(binding_id, now=instant)
    if eligible is None:
        return {'state': 'unavailable', 'entries': None}
    binding, source = eligible
    snapshot = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki',
        asset_key=binding.asset_key,
        signal_key=SIGNAL_KEY,
    ).first()
    if snapshot is None or snapshot.status != 'ready':
        return {'state': 'unavailable', 'entries': None}
    created = _persisted_utc(snapshot.generated_at)
    expires = _persisted_utc(snapshot.expires_at)
    if created is None or expires is None or not created <= instant <= expires or expires - created != _TTL:
        return {'state': 'stale', 'entries': None}
    payload = _qualified_snapshot_payload(snapshot.payload_json, binding=binding, source=source)
    if payload is None:
        return {'state': 'unavailable', 'entries': None}
    entries = payload.get('entries')
    if not isinstance(entries, list) or len(entries) > _MAX_ALERTS:
        return {'state': 'unavailable', 'entries': None}
    if payload['status'] == 'unobserved':
        return (
            {'state': 'unobserved', 'entries': None}
            if not entries
            else {
                'state': 'unavailable',
                'entries': None,
            }
        )
    if not entries:
        return {'state': 'unavailable', 'entries': None}
    handles: list[str] = []
    for entry in entries:
        handle = _validated_snapshot_alert_handle(entry, created=created, instant=instant)
        if handle is None:
            return {'state': 'unavailable', 'entries': None}
        handles.append(handle)
    if len(handles) != len(set(handles)):
        return {'state': 'unavailable', 'entries': None}
    return {'state': 'fresh', 'entries': [dict(entry) for entry in entries]}
