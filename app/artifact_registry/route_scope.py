from __future__ import annotations

from typing import Any

from flask import abort, request

from app.artifact_registry.presentation_analytics import AnalyticsAlertFilters
from app.artifact_registry.presentation_common import _providers as _active_registry_sources
from app.artifact_registry.security.cve_impact import CveImpactFilters
from app.artifact_registry.security.presentation import _providers as _eligible_security_sources


def _overview_provider_id() -> int | None:
    """Treat malformed explicit scope IDs as unavailable, not All Providers."""
    raw = request.args.get('provider_id')
    if raw is None or not raw.strip():
        return None
    try:
        provider_id = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if provider_id < 1:
        abort(404)
    return provider_id


def _inventory_source_id() -> int | None:
    """An invalid explicit Registry source filter must not expand to all providers."""
    raw = request.args.get('source_id')
    if raw is None or not raw.strip():
        return None
    try:
        source_id = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if source_id < 1:
        abort(404)
    return source_id


def _security_source_id(*, from_form: bool = False) -> int | None:
    """Explicit malformed source filters must never widen Security to the fleet."""
    values = request.form if from_form else request.args
    raw = values.get('source_id')
    if raw is None or not str(raw).strip():
        return None
    try:
        source_id = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if source_id < 1:
        abort(404)
    if from_form and not any(int(item.id) == source_id for item in _eligible_security_sources()):
        # Reject unavailable selected-view context *before* dispatching a fleet job.
        abort(404)
    return source_id


def _runtime_scope_id(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if value < 1:
        abort(404)
    if name == 'source_id' and not any(int(source.id) == value for source in _active_registry_sources()):
        abort(404)
    return value


def _runtime_topology_filters() -> dict[str, Any]:
    return {
        'search': request.args.get('q', '', type=str),
        'source_id': _runtime_scope_id('source_id'),
        'cluster_id': request.args.get('cluster_id', '', type=str),
        'namespace': request.args.get('namespace', '', type=str),
        'match_type': request.args.get('match_type', '', type=str),
        'exposure': request.args.get('exposure', '', type=str),
        'artifact_id': _runtime_scope_id('artifact_id'),
    }


def _analytics_provider_id() -> int | None:
    """Explicit scope is fail-closed; invalid IDs must not expand to the fleet."""
    value = request.args.get('provider_id')
    if value is None or value == '':
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 18:
        abort(404)
    if int(value) <= 0:
        abort(404)
    return int(value)

def _analytics_alert_filters() -> AnalyticsAlertFilters:
    """Read allowed alert dimensions from the current Registry view request."""
    return AnalyticsAlertFilters(
        severity=request.args.get('alert_severity', 'all', type=str),
        state=request.args.get('alert_state', 'all', type=str),
        source=request.args.get('alert_source', 'all', type=str),
    )


def _cve_impact_filters() -> CveImpactFilters:
    """Preserve separate scanner and Kubernetes runtime search parameters."""
    return CveImpactFilters(
        finding_search=request.args.get('finding_q', '', type=str),
        finding_severity=request.args.get('finding_severity', '', type=str),
        runtime_search=request.args.get('runtime_q', '', type=str),
        runtime_match=request.args.get('runtime_match', '', type=str),
    )
