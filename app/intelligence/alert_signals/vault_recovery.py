"""Provider-owned signed positive recovery evidence collected by the existing worker.

A receipt is explicit evidence of resolution, not a derived absence signal.
Only the existing worker owns the correlation key. No raw provider receipt,
fingerprint, rule reference, or signature is persisted or sent to the UI.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.extensions.db import db
from app.intelligence.alert_signals.vault_authority import read_signed_authority, receipt_time
from app.intelligence.alert_signals.vault_source import (
    _HANDLE,
    _MAX_ALERTS,
    _TTL,
    _UnsafeSource,
    _locked_observation_snapshot,
    _normalize,
    _persisted_utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_signal import AlertSignalSnapshot
from app.models.integration import IntegrationBinding, IntegrationInstance

SIGNAL_KEY = 'secrets_pki.vault_alertmanager_recovery'
_SCHEMA = 'kaori.vault.alert_recovery.v1'
_DIGEST = re.compile(r'[a-f0-9]{64}')


def _exact_receipt(
    payload: dict[str, Any], *, binding: IntegrationBinding, source: IntegrationInstance
) -> bool:
    binding_revision = _persisted_utc(binding.updated_at)
    source_revision = _persisted_utc(source.updated_at)
    return (
        binding_revision is not None
        and source_revision is not None
        and set(payload) == {
            'schema', 'state', 'binding_id', 'instance_id', 'source_id',
            'binding_revision', 'source_revision', 'issued_at', 'expires_at', 'complete', 'entries'
        }
        and type(payload['binding_id']) is int
        and payload['binding_id'] == binding.id
        and type(payload['instance_id']) is int
        and str(payload['instance_id']) == binding.asset_key
        and type(payload['source_id']) is int
        and payload['source_id'] == source.id
        and receipt_time(payload['binding_revision']) == binding_revision
        and receipt_time(payload['source_revision']) == source_revision
        and payload['complete'] is True
    )


def _project_entries(
    entries: object, *, binding: IntegrationBinding, source_id: int, key: bytes, observed: datetime, issued: datetime
) -> list[dict[str, str]] | None:
    if not isinstance(entries, list) or not 0 <= len(entries) <= _MAX_ALERTS:
        return None
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'fingerprint', 'starts_at', 'resolved_at', 'rule_ref', 'state'}:
            return None
        starts, resolved = receipt_time(entry['starts_at']), receipt_time(entry['resolved_at'])
        rule_ref = entry['rule_ref']
        if (
            entry['state'] != 'resolved'
            or starts is None or resolved is None or not starts <= resolved <= min(observed, issued)
            or not isinstance(rule_ref, str) or not _DIGEST.fullmatch(rule_ref)
        ):
            return None
        try:
            normalized = _normalize(
                [{
                    'labels': {'vault_instance': binding.asset_key, 'severity': 'info'},
                    'status': {'state': 'active'},
                    'fingerprint': entry['fingerprint'],
                    'startsAt': entry['starts_at'],
                }],
                vault_id=binding.asset_key,
                source_id=source_id,
                hmac_key=key,
                now=observed,
            )
        except _UnsafeSource:
            return None
        handle = normalized['entries'][0]['handle']
        if handle in seen:
            return None
        seen.add(handle)
        result.append({'handle': handle, 'resolved_at': resolved.isoformat()})
    return result


def _recovery_snapshot(asset_key: str, *, lock: bool = False) -> AlertSignalSnapshot | None:
    query = AlertSignalSnapshot.query.filter_by(
        domain='secrets_pki', asset_key=asset_key, signal_key=SIGNAL_KEY
    ).populate_existing()
    return (query.with_for_update() if lock else query).first()


def collect_vault_recovery(
    binding_id: int, *, key: bytes, observed: datetime, now: datetime
) -> str:
    """Commit only an independently signed record linked to the current GET generation."""
    try:
        eligible = _validated_binding(binding_id, now=now, lock=True)
        if eligible is None:
            return 'unavailable'
        binding, source = eligible
        active = _locked_observation_snapshot(binding.asset_key)
        if active is None or active.status != 'ready' or _persisted_utc(active.generated_at) != observed:
            return 'unavailable'
        if read_vault_alert_observations(binding_id=binding.id, now=now)['state'] not in ('fresh', 'unobserved'):
            return 'unavailable'
        signed = read_signed_authority(f'recovery-{binding.id}', schema=_SCHEMA, now=now)
        if signed is None:
            return 'unavailable'
        payload, evidence_ref = signed
        if not _exact_receipt(payload, binding=binding, source=source):
            return 'unavailable'
        issued = receipt_time(payload['issued_at'])
        expires = receipt_time(payload['expires_at'])
        if issued is None or expires is None or min(expires, observed + _TTL) <= now:
            return 'unavailable'
        entries = _project_entries(
            payload['entries'], binding=binding, source_id=source.id, key=key, observed=observed, issued=issued
        )
        if entries is None:
            return 'unavailable'
        snapshot = _recovery_snapshot(binding.asset_key, lock=True)
        if snapshot is None:
            snapshot = AlertSignalSnapshot(domain='secrets_pki', asset_key=binding.asset_key, signal_key=SIGNAL_KEY)
            db.session.add(snapshot)
        previous = _persisted_utc(snapshot.generated_at)
        if previous is not None and previous >= observed:
            return 'unavailable'
        snapshot.status = 'ready'
        snapshot.generated_at = observed
        snapshot.expires_at = min(expires, observed + _TTL)
        snapshot.last_attempt_at = observed
        snapshot.last_error = None
        snapshot.payload_json = {
            'schema_version': 2,
            'binding_id': binding.id,
            'source_id': source.id,
            'binding_revision': payload['binding_revision'],
            'source_revision': payload['source_revision'],
            'evidence_ref': evidence_ref,
            'issued_at': issued.isoformat(),
            'entries': entries,
        }
        db.session.commit()
        return 'qualified'
    finally:
        db.session.rollback()


def read_vault_recovery(
    *, binding: IntegrationBinding, source: IntegrationInstance, observed: datetime, now: datetime
) -> dict[str, Any] | None:
    """Read under the caller's binding and active-generation locks; fail closed."""
    snapshot = _recovery_snapshot(binding.asset_key, lock=True)
    if snapshot is None or snapshot.status != 'ready' or _persisted_utc(snapshot.generated_at) != observed:
        return None
    expires = _persisted_utc(snapshot.expires_at)
    payload = snapshot.payload_json
    if expires is None or not observed <= now < expires <= observed + _TTL or not isinstance(payload, dict):
        return None
    if set(payload) != {
        'schema_version', 'binding_id', 'source_id', 'binding_revision', 'source_revision', 'evidence_ref', 'issued_at', 'entries'
    }:
        return None
    if (
        type(payload['schema_version']) is not int or payload['schema_version'] != 2
        or type(payload['binding_id']) is not int or payload['binding_id'] != binding.id
        or type(payload['source_id']) is not int or payload['source_id'] != source.id
        or receipt_time(payload['binding_revision']) != _persisted_utc(binding.updated_at)
        or receipt_time(payload['source_revision']) != _persisted_utc(source.updated_at)
        or not isinstance(payload['evidence_ref'], str) or not _DIGEST.fullmatch(payload['evidence_ref'])
    ):
        return None
    issued = receipt_time(payload['issued_at'])
    if issued is None or issued > now:
        return None
    # Removing, replacing, or revoking a receipt immediately blocks mutation,
    # even during the short committed snapshot lifetime.
    signed = read_signed_authority(f'recovery-{binding.id}', schema=_SCHEMA, now=now)
    if signed is None or signed[1] != payload['evidence_ref'] or not _exact_receipt(
        signed[0], binding=binding, source=source
    ):
        return None
    if receipt_time(signed[0]['issued_at']) != issued:
        return None
    entries = payload['entries']
    if not isinstance(entries, list) or len(entries) > _MAX_ALERTS:
        return None
    handles: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'handle', 'resolved_at'}:
            return None
        handle, resolved = entry['handle'], receipt_time(entry['resolved_at'])
        if not isinstance(handle, str) or not _HANDLE.fullmatch(handle) or handle in handles:
            return None
        if resolved is None or resolved > min(observed, issued):
            return None
        handles.add(handle)
    return payload
