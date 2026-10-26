"""Vault instance Metrics Source consumer qualification.

Prometheus/Thanos owns historical data, never the Vault provider adapter.
This profile requires an explicitly attached, query-visible stable KAORI
instance label and refuses ambiguous or unobserved Vault identity series.
"""

from __future__ import annotations

import math
from time import time
from typing import Any

from app.extensions.db import db
from app.integrations.binding_selectors import BindingMatcher, parse_matchers
from app.integrations.observability.metrics_source.binding_profiles import BindingValidationProfile
from app.integrations.observability.metrics_source.binding_validators.contracts import BindingValidationAssessment
from app.models.integration import IntegrationBinding, IntegrationInstance

_IDENTITY_LABEL = 'vault_instance'
_IDENTITY_METRIC = 'vault_core_active'
_MAX_SAMPLE_AGE_SECONDS = 300

_HISTORY_LOOKBACK_SECONDS = 3600
_HISTORY_STEP_SECONDS = 300
_HISTORY_MAX_SAMPLES = 16


def _historical_window_assessment(
    *,
    client: Any,
    expression: str,
    integration_id: int,
    now_epoch: float,
) -> dict[str, Any]:
    """Bounded one-hour query_range; only sanitized summaries are persisted.

    This never qualifies longer historical retention, HA topology, trends or
    Vault API readiness. Instant binding qualification is separate.
    """
    base = {
        'historical_query_readiness': 'not_validated',
        'retention_coverage': 'not_validated',
    }
    query_range = getattr(client, 'query_range', None)
    if not callable(query_range):
        return base

    def unsupported(status: str) -> dict[str, Any]:
        return {
            'historical_query_readiness': status,
            'retention_coverage': 'not_qualified',
        }

    end = int(now_epoch)
    start = end - _HISTORY_LOOKBACK_SECONDS
    try:
        payload = query_range(
            expression,
            str(start),
            str(end),
            str(_HISTORY_STEP_SECONDS),
        )
    except Exception:
        # A raw Metrics Source exception may contain URL/credentials/paths.
        return unsupported('unavailable')
    if not isinstance(payload, dict) or payload.get('status') != 'success':
        return unsupported('unavailable')
    data = payload.get('data')
    if not isinstance(data, dict) or data.get('resultType') != 'matrix':
        return unsupported('unavailable')
    results = data.get('result')
    if not isinstance(results, list):
        return unsupported('unavailable')
    if len(results) > 1:
        return unsupported('ambiguous')
    if not results:
        return unsupported('incomplete')
    record = results[0]
    if not isinstance(record, dict):
        return unsupported('incomplete')
    labels = record.get('metric')
    if (
        not isinstance(labels, dict)
        or labels.get(_IDENTITY_LABEL) != str(integration_id)
        or labels.get('__name__') not in {None, _IDENTITY_METRIC}
    ):
        return unsupported('ambiguous')
    values = record.get('values')
    if not isinstance(values, list) or not 1 <= len(values) <= _HISTORY_MAX_SAMPLES:
        return unsupported('incomplete')
    timestamps: list[float] = []
    for point in values:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            return unsupported('incomplete')
        try:
            timestamp, value = float(point[0]), float(point[1])
        except (TypeError, ValueError, OverflowError):
            return unsupported('incomplete')
        if (
            not math.isfinite(timestamp)
            or not math.isfinite(value)
            or value not in {0.0, 1.0}
            or not start - 60 <= timestamp <= end + 60
            or (timestamps and timestamp <= timestamps[-1])
        ):
            return unsupported('incomplete')
        timestamps.append(timestamp)
    if (
        timestamps[0] > start + _HISTORY_STEP_SECONDS
        or timestamps[-1] < end - _HISTORY_STEP_SECONDS
        or any(right - left > 2 * _HISTORY_STEP_SECONDS for left, right in zip(timestamps, timestamps[1:]))
    ):
        return unsupported('incomplete')
    return {
        'historical_query_readiness': 'recent_hour_qualified',
        'retention_coverage': 'one_hour_observed_only',
        'historical_window_seconds': _HISTORY_LOOKBACK_SECONDS,
        'historical_step_seconds': _HISTORY_STEP_SECONDS,
        'historical_sample_count': len(timestamps),
    }


def _assessment(status: str, message: str, *, state: str, matched: int = 0) -> BindingValidationAssessment:
    return BindingValidationAssessment(
        status=status,
        message=message,
        matched_series=matched,
        matched_signal=_IDENTITY_METRIC if matched else None,
        evidence={
            'asset_profile': 'vault-telemetry-v1',
            'source_identity': {'label': _IDENTITY_LABEL, 'status': state},
            'selector_isolation': state,
            'metrics_readiness': {'status': 'unverified' if status != 'ready' else 'ready'},
            'historical_query_readiness': 'not_validated',
            'retention_coverage': 'not_validated',
            'alert_source_readiness': 'not_evaluated',
            'available_capabilities': [],
            'capability_assessments': [],
        },
    )


def _identity_matcher(binding: IntegrationBinding, integration_id: int) -> BindingMatcher | None:
    raw = binding.selector_json
    entries = raw.get('matchers') if isinstance(raw, dict) else None
    if not isinstance(entries, list) or len(entries) != 1:
        return None
    parsed = parse_matchers(raw)
    if len(parsed) != 1:
        return None
    matcher = parsed[0]
    if matcher.label != _IDENTITY_LABEL or matcher.operator != '=' or matcher.value != str(integration_id):
        return None
    return matcher


def validate_vault_metrics_binding(
    *,
    client: Any,
    binding: IntegrationBinding,
    profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    key = str(binding.asset_key or '')
    if not key.isascii() or not key.isdecimal() or len(key) > 10:
        return _assessment('blocked', 'Vault binding requires a canonical instance ID.', state='invalid_asset')
    identity = db.session.get(IntegrationInstance, int(key))
    if (
        identity is None
        or identity.integration_type != 'secrets_pki'
        or identity.provider_key != 'vault'
        or identity.lifecycle_status != 'active'
        or not identity.enabled
    ):
        return _assessment('blocked', 'The bound Vault provider identity is no longer active.', state='invalid_asset')
    matcher = _identity_matcher(binding, identity.id)
    if matcher is None:
        return _assessment(
            'blocked',
            'Vault telemetry needs the exact vault_instance label matching the canonical KAORI instance ID.',
            state='unqualified_selector',
        )
    expression = f'{_IDENTITY_METRIC}{{{matcher.as_filter()}}}'
    try:
        payload = client.query(expression)
    except Exception:
        # Never leak raw provider URLs or response bodies into integration evidence.
        return _assessment(
            'degraded', 'Vault identity metric query failed; source remains unverified.', state='query_unavailable'
        )
    if not isinstance(payload, dict) or payload.get('status') != 'success':
        return _assessment('degraded', 'Vault identity metric query did not succeed.', state='query_unavailable')
    data = payload.get('data')
    if not isinstance(data, dict) or data.get('resultType') != 'vector':
        return _assessment(
            'degraded', 'Vault identity metric returned an unsupported response type.', state='unsupported_response'
        )
    results = data.get('result')
    if not isinstance(results, list) or len(results) > 1:
        return _assessment(
            'blocked', 'Vault selector is ambiguous or metrics evidence is malformed.', state='ambiguous_identity'
        )
    if not results:
        return _assessment('degraded', 'No Vault core identity signal matches the approved instance.', state='no_match')
    record = results[0]
    if not isinstance(record, dict) or not isinstance(record.get('metric'), dict):
        return _assessment('blocked', 'Vault metric identity cannot be verified.', state='invalid_response')
    labels = record['metric']
    if labels.get(_IDENTITY_LABEL) != str(identity.id) or labels.get('__name__') not in {
        None,
        _IDENTITY_METRIC,
    }:
        return _assessment('blocked', 'Vault metric identity does not match the configured provider.', state='mismatch')
    sample = record.get('value')
    if not isinstance(sample, (list, tuple)) or len(sample) != 2:
        return _assessment('degraded', 'Vault identity sample is malformed.', state='invalid_sample')
    try:
        observed_epoch = float(sample[0])
        active_value = float(sample[1])
    except (TypeError, ValueError, OverflowError):
        return _assessment('degraded', 'Vault identity sample is not numeric.', state='invalid_sample')
    if not math.isfinite(observed_epoch) or not math.isfinite(active_value) or active_value not in {0.0, 1.0}:
        return _assessment('degraded', 'Vault core active sample is invalid.', state='invalid_sample')
    delta = time() - observed_epoch
    if delta < -60 or delta > _MAX_SAMPLE_AGE_SECONDS:
        return _assessment('degraded', 'Vault identity telemetry sample is stale.', state='stale_sample')
    instant = _assessment(
        'ready',
        f'{profile.label} matched one time-qualified Vault node identity; long-term retention is not validated.',
        state='single_node_confirmed',
        matched=1,
    )
    history = _historical_window_assessment(
        client=client,
        expression=expression,
        integration_id=identity.id,
        now_epoch=time(),
    )
    return BindingValidationAssessment(
        status=instant.status,
        message=instant.message,
        matched_series=instant.matched_series,
        matched_signal=instant.matched_signal,
        evidence={**instant.evidence, **history},
    )
