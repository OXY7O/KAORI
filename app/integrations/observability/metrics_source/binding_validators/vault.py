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
    if (
        matcher.label != _IDENTITY_LABEL
        or matcher.operator != '='
        or matcher.value != str(integration_id)
    ):
        return None
    return matcher


def validate_vault_metrics_binding(
    *, client: Any, binding: IntegrationBinding, profile: BindingValidationProfile,
) -> BindingValidationAssessment:
    key = str(binding.asset_key or '')
    if not key.isascii() or not key.isdecimal() or len(key) > 10:
        return _assessment('blocked', 'Vault binding requires a canonical instance ID.', state='invalid_asset')
    identity = db.session.get(IntegrationInstance, int(key))
    if (
        identity is None or identity.integration_type != 'secrets_pki'
        or identity.provider_key != 'vault'
        or identity.lifecycle_status != 'active' or not identity.enabled
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
        return _assessment('degraded', 'Vault identity metric query failed; source remains unverified.', state='query_unavailable')
    if not isinstance(payload, dict) or payload.get('status') != 'success':
        return _assessment('degraded', 'Vault identity metric query did not succeed.', state='query_unavailable')
    data = payload.get('data')
    if not isinstance(data, dict) or data.get('resultType') != 'vector':
        return _assessment('degraded', 'Vault identity metric returned an unsupported response type.', state='unsupported_response')
    results = data.get('result')
    if not isinstance(results, list) or len(results) > 1:
        return _assessment('blocked', 'Vault selector is ambiguous or metrics evidence is malformed.', state='ambiguous_identity')
    if not results:
        return _assessment('degraded', 'No Vault core identity signal matches the approved instance.', state='no_match')
    record = results[0]
    if not isinstance(record, dict) or not isinstance(record.get('metric'), dict):
        return _assessment('blocked', 'Vault metric identity cannot be verified.', state='invalid_response')
    labels = record['metric']
    if labels.get(_IDENTITY_LABEL) != str(identity.id) or labels.get('__name__') not in {
        None, _IDENTITY_METRIC,
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
    return _assessment(
        'ready',
        f'{profile.label} matched one time-qualified Vault node identity; historical retention is not yet validated.',
        state='single_node_confirmed', matched=1,
    )
