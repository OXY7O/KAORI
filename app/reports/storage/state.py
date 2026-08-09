from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from threading import Lock
from typing import Any, cast

from flask import current_app
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

READINESS_KEY_PREFIX = 'kaori:reports:storage-readiness:'
_REDIS_CLIENTS: dict[str, Redis] = {}
_REDIS_CLIENTS_LOCK = Lock()


def _redis_client() -> Redis | None:
    redis_url = str(current_app.config.get('REDIS_URL') or '').strip()
    if not redis_url:
        return None
    with _REDIS_CLIENTS_LOCK:
        client = _REDIS_CLIENTS.get(redis_url)
        if client is None:
            client = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _REDIS_CLIENTS[redis_url] = client
        return client


def _stale_after_seconds() -> int:
    try:
        value = int(current_app.config.get('REPORT_STORAGE_HEALTH_STALE_SECONDS', 120) or 120)
    except (TypeError, ValueError):
        value = 120
    return max(30, min(value, 3600))


def _state_ttl_seconds() -> int:
    try:
        value = int(current_app.config.get('REPORT_STORAGE_HEALTH_STATE_TTL_SECONDS', 600) or 600)
    except (TypeError, ValueError):
        value = 600
    return max(_stale_after_seconds() * 2, min(value, 86400))


def get_storage_config_fingerprint(backend_name: str) -> str:
    normalized = str(backend_name or '').strip().lower()
    if normalized == 's3':
        parts = (
            normalized,
            str(current_app.config.get('REPORT_S3_BUCKET', '') or ''),
            str(current_app.config.get('REPORT_S3_ENDPOINT_URL', '') or ''),
            str(current_app.config.get('REPORT_S3_REGION', '') or ''),
            str(current_app.config.get('REPORT_S3_PREFIX', '') or ''),
            str(current_app.config.get('REPORT_S3_ACCESS_KEY_ID', '') or ''),
            str(current_app.config.get('REPORT_S3_SECRET_ACCESS_KEY', '') or ''),
            str(bool(current_app.config.get('REPORT_S3_FORCE_PATH_STYLE', False))),
        )
    else:
        parts = (
            normalized,
            str(current_app.config.get('REPORT_LOCAL_STORAGE_DIR', '') or ''),
        )
    digest = hashlib.sha256('\x1f'.join(parts).encode('utf-8')).hexdigest()
    return digest[:16]


def _state_key(backend_name: str) -> str:
    normalized = str(backend_name or 'unknown').strip().lower() or 'unknown'
    fingerprint = get_storage_config_fingerprint(normalized)
    return f'{READINESS_KEY_PREFIX}{normalized}:{fingerprint}'


def _parse_checked_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def decorate_storage_readiness(
    status: dict[str, Any],
    *,
    source: str,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    now = checked_at or datetime.now(UTC)
    decorated = dict(status)
    decorated['checked_at'] = now.isoformat()
    decorated['source'] = str(source or 'direct')
    decorated['config_fingerprint'] = get_storage_config_fingerprint(str(status.get('backend') or 'unknown'))
    decorated['stale_after_seconds'] = _stale_after_seconds()
    decorated['age_seconds'] = 0
    decorated['stale'] = False
    return decorated


def publish_shared_report_storage_status(
    status: dict[str, Any],
    *,
    source: str,
) -> dict[str, Any]:
    decorated = decorate_storage_readiness(status, source=source)
    client = _redis_client()
    if client is None:
        return decorated
    try:
        client.set(
            _state_key(str(decorated.get('backend') or 'unknown')),
            json.dumps(decorated, separators=(',', ':'), default=str),
            ex=_state_ttl_seconds(),
        )
    except RedisError:
        logger.warning('Could not publish shared report-storage readiness state.', exc_info=True)
    return decorated


def get_shared_report_storage_status(
    backend_name: str,
    *,
    allow_stale: bool = False,
) -> dict[str, Any] | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.get(_state_key(backend_name))
    except RedisError:
        logger.debug('Shared report-storage readiness state is unavailable.', exc_info=True)
        return None
    if not raw:
        return None
    try:
        payload = json.loads(cast(str | bytes | bytearray, raw))
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get('config_fingerprint') != get_storage_config_fingerprint(backend_name):
        return None

    checked_at = _parse_checked_at(payload.get('checked_at'))
    if checked_at is None:
        return None
    age_seconds = max(int((datetime.now(UTC) - checked_at).total_seconds()), 0)
    stale = age_seconds > _stale_after_seconds()
    payload['age_seconds'] = age_seconds
    payload['stale'] = stale
    payload['stale_after_seconds'] = _stale_after_seconds()
    if stale and not allow_stale:
        return None
    return payload


def clear_shared_report_storage_status(backend_name: str) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.delete(_state_key(backend_name))
    except RedisError:
        logger.debug('Could not clear shared report-storage readiness state.', exc_info=True)


def format_storage_check_age(status: dict[str, Any]) -> str:
    try:
        age = max(int(status.get('age_seconds') or 0), 0)
    except (TypeError, ValueError):
        age = 0
    if age < 10:
        return 'Checked just now'
    if age < 60:
        return f'Checked {age}s ago'
    minutes = age // 60
    if minutes < 60:
        return f'Checked {minutes}m ago'
    hours = minutes // 60
    return f'Checked {hours}h ago'


def format_storage_check_source(status: dict[str, Any]) -> str:
    source = str(status.get('source') or 'direct').strip().lower()
    labels = {
        'periodic': 'Periodic Monitor',
        'manual_verification': 'Manual Verification',
        'manual_verification_failure': 'Manual Verification Failure',
        'artifact_write_failure': 'Artifact Write Failure',
        'artifact_read_failure': 'Artifact Read Failure',
        'operation_failure': 'Artifact Operation',
        'direct': 'Direct Probe',
    }
    return labels.get(source, source.replace('_', ' ').title() or 'Direct Probe')
