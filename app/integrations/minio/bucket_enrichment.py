from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError


@dataclass(frozen=True, slots=True)
class BucketConfigurationEvidence:
    versioning_state: str
    immutability_state: str
    encryption_state: str
    lifecycle_state: str
    replication_state: str
    access_policy_state: str
    exposure_state: str
    native_rows: list[dict[str, Any]]
    gaps: list[str]


def optional_bucket_call(
    client,
    method_name: str,
    bucket_name: str,
    *,
    not_configured_codes: set[str],
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = getattr(client, method_name)(Bucket=bucket_name)
        return payload if isinstance(payload, dict) else {}, None
    except ClientError as exc:
        code = str((exc.response.get('Error') or {}).get('Code') or '')
        if code in not_configured_codes:
            return {}, 'not_configured'
        return None, 'not_collected'
    except (BotoCoreError, OSError):
        return None, 'not_collected'


def _principal_has_wildcard(principal: Any) -> bool:
    if principal == '*':
        return True
    if isinstance(principal, list):
        return any(item == '*' for item in principal)
    if isinstance(principal, dict):
        return any(_principal_has_wildcard(value) for value in principal.values())
    return False


def bucket_policy_exposure(policy_text: str | None) -> str:
    if not policy_text:
        return 'private'
    try:
        payload = json.loads(policy_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return 'not_collected'
    statements = payload.get('Statement') if isinstance(payload, dict) else None
    if not isinstance(statements, list):
        statements = [statements] if isinstance(statements, dict) else []
    for statement in statements:
        if not isinstance(statement, dict) or str(statement.get('Effect') or '').lower() != 'allow':
            continue
        if _principal_has_wildcard(statement.get('Principal')):
            return 'restricted' if statement.get('Condition') else 'public'
    return 'private'


def _versioning(client, name: str) -> tuple[str, dict[str, Any], list[str]]:
    payload, gap = optional_bucket_call(client, 'get_bucket_versioning', name, not_configured_codes=set())
    if gap:
        return gap, {'label': 'Versioning', 'value': gap.replace('_', ' ').title()}, ['Versioning']
    value = str((payload or {}).get('Status') or 'Not Configured')
    state = {'Enabled': 'enabled', 'Suspended': 'suspended'}.get(value, 'not_configured')
    return state, {'label': 'Versioning', 'value': value}, []


def _encryption(client, name: str) -> tuple[str, dict[str, Any], list[str]]:
    payload, gap = optional_bucket_call(
        client,
        'get_bucket_encryption',
        name,
        not_configured_codes={'ServerSideEncryptionConfigurationNotFoundError', 'NoSuchServerSideEncryptionConfiguration'},
    )
    if gap:
        gaps = ['Encryption'] if gap == 'not_collected' else []
        return gap, {'label': 'Encryption', 'value': gap.replace('_', ' ').title()}, gaps
    rules = ((payload or {}).get('ServerSideEncryptionConfiguration') or {}).get('Rules') or []
    algorithms = sorted(
        {
            str((rule.get('ApplyServerSideEncryptionByDefault') or {}).get('SSEAlgorithm') or '').strip()
            for rule in rules
            if str((rule.get('ApplyServerSideEncryptionByDefault') or {}).get('SSEAlgorithm') or '').strip()
        }
    )
    state = 'configured' if rules else 'not_configured'
    value = ', '.join(algorithms) if algorithms else state.replace('_', ' ').title()
    return state, {'label': 'Encryption', 'value': value}, []


def _immutability(client, name: str) -> tuple[str, dict[str, Any], list[str]]:
    payload, gap = optional_bucket_call(
        client,
        'get_object_lock_configuration',
        name,
        not_configured_codes={'ObjectLockConfigurationNotFoundError', 'NoSuchObjectLockConfiguration'},
    )
    if gap:
        gaps = ['Immutability'] if gap == 'not_collected' else []
        return gap, {'label': 'Object Lock', 'value': gap.replace('_', ' ').title()}, gaps
    config = (payload or {}).get('ObjectLockConfiguration') or {}
    state = 'enabled' if config.get('ObjectLockEnabled') == 'Enabled' else 'not_configured'
    retention = (config.get('Rule') or {}).get('DefaultRetention') or {}
    value = 'Enabled' if state == 'enabled' else 'Not Configured'
    if retention:
        parts = [
            str(retention.get('Mode') or '').strip(),
            f'{retention.get("Days")} Days' if retention.get('Days') else '',
            f'{retention.get("Years")} Years' if retention.get('Years') else '',
        ]
        label = ' · '.join(part for part in parts if part)
        if label:
            value = f'{value} · {label}'
    return state, {'label': 'Object Lock', 'value': value}, []


def _rules_state(client, name: str, method: str, key: str, missing: set[str], label: str) -> tuple[str, dict[str, Any], list[str]]:
    payload, gap = optional_bucket_call(client, method, name, not_configured_codes=missing)
    data = payload or {}
    if key == 'ReplicationConfiguration':
        rules = (data.get(key) or {}).get('Rules') or []
    else:
        rules = data.get(key) or []
    state = gap or ('configured' if rules else 'not_configured')
    gaps = [label] if gap == 'not_collected' else []
    return state, {'label': f'{label} Rules', 'value': len(rules)}, gaps


def _policy(client, name: str) -> tuple[str, str, list[dict[str, Any]], list[str]]:
    payload, gap = optional_bucket_call(client, 'get_bucket_policy', name, not_configured_codes={'NoSuchBucketPolicy'})
    if gap:
        access_state = gap
        exposure = 'private' if gap == 'not_configured' else gap
        value = gap.replace('_', ' ').title()
        gaps = ['Access Policy'] if gap == 'not_collected' else []
    else:
        text = str((payload or {}).get('Policy') or '').strip()
        access_state = 'configured' if text else 'not_configured'
        exposure = bucket_policy_exposure(text)
        value = 'Configured' if text else 'Not Configured'
        gaps = []
    rows = [
        {'label': 'Bucket Policy', 'value': value},
        {'label': 'Policy Exposure', 'value': exposure.replace('_', ' ').title()},
    ]
    return access_state, exposure, rows, gaps


def collect_bucket_configuration(client, name: str) -> BucketConfigurationEvidence:
    versioning, versioning_row, versioning_gaps = _versioning(client, name)
    encryption, encryption_row, encryption_gaps = _encryption(client, name)
    immutability, lock_row, lock_gaps = _immutability(client, name)
    lifecycle, lifecycle_row, lifecycle_gaps = _rules_state(
        client, name, 'get_bucket_lifecycle_configuration', 'Rules', {'NoSuchLifecycleConfiguration'}, 'Lifecycle'
    )
    replication, replication_row, replication_gaps = _rules_state(
        client,
        name,
        'get_bucket_replication',
        'ReplicationConfiguration',
        {'ReplicationConfigurationNotFoundError', 'NoSuchReplicationConfiguration'},
        'Replication',
    )
    access_policy, exposure, policy_rows, policy_gaps = _policy(client, name)
    return BucketConfigurationEvidence(
        versioning_state=versioning,
        immutability_state=immutability,
        encryption_state=encryption,
        lifecycle_state=lifecycle,
        replication_state=replication,
        access_policy_state=access_policy,
        exposure_state=exposure,
        native_rows=[versioning_row, encryption_row, lock_row, lifecycle_row, replication_row, *policy_rows],
        gaps=[*versioning_gaps, *encryption_gaps, *lock_gaps, *lifecycle_gaps, *replication_gaps, *policy_gaps],
    )
