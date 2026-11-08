from __future__ import annotations

from typing import Any

from app.artifact_registry.presentation_analytics import (
    build_analytics,
    build_analytics_shell,
)
from app.artifact_registry.presentation_common import (
    FRESHNESS_HOURS,
    _analytics_payload,
    _analytics_snapshot_view,
    _aware_datetime,
    _fmt_bytes,
    _freshness_value,
    _human_time,
    _latest_registry_analytics,
    _overview_kpi_values,
    _overview_scope_context,
    _providers,
    _registry_alerts,
    _registry_capacity_views,
    _registry_recommended_actions,
    _registry_reporting,
    _state_view,
)
from app.artifact_registry.presentation_governance import (
    _policy_state_view,
    build_governance,
)
from app.artifact_registry.presentation_inventory import (
    _artifact_row,
    _decorate_inventory_provider_provenance,
    _inventory_base_context,
    _inventory_detail_provider_context,
    _inventory_fleet_readings,
    _inventory_resource_catalog,
    _inventory_resource_posture_metrics,
    _inventory_snapshot_context,
    _project_row,
    _repository_row,
    build_inventory,
    build_inventory_artifact_detail,
    build_inventory_overview,
    build_inventory_project_detail,
    build_inventory_repository_detail,
)
from app.artifact_registry.presentation_overview import (
    _overview_capacity_projection,
    _overview_operations_projection,
    _provider_health_projection,
    build_overview,
    build_overview_section,
)
from app.artifact_registry.presentation_runtime import (
    _runtime_match_state,
    _runtime_parse_observed_at,
    _runtime_prerequisite_guidance,
    _runtime_security_index,
    _runtime_security_state,
    build_runtime_binding_detail,
    build_runtime_usage,
)

__all__ = [
    'FRESHNESS_HOURS',
    '_analytics_payload',
    '_analytics_snapshot_view',
    '_artifact_row',
    '_aware_datetime',
    '_decorate_inventory_provider_provenance',
    '_fmt_bytes',
    '_freshness_value',
    '_human_time',
    '_inventory_base_context',
    '_inventory_detail_provider_context',
    '_inventory_fleet_readings',
    '_inventory_resource_catalog',
    '_inventory_resource_posture_metrics',
    '_inventory_snapshot_context',
    '_latest_registry_analytics',
    '_overview_capacity_projection',
    '_overview_kpi_values',
    '_overview_operations_projection',
    '_overview_scope_context',
    '_policy_state_view',
    '_project_row',
    '_provider_health_projection',
    '_providers',
    '_registry_alerts',
    '_registry_capacity_views',
    '_registry_recommended_actions',
    '_registry_reporting',
    '_repository_row',
    '_runtime_match_state',
    '_runtime_parse_observed_at',
    '_runtime_prerequisite_guidance',
    '_runtime_security_index',
    '_runtime_security_state',
    '_state_view',
    'build_analytics',
    'build_analytics_shell',
    'build_governance',
    'build_inventory',
    'build_inventory_artifact_detail',
    'build_inventory_overview',
    'build_inventory_project_detail',
    'build_inventory_repository_detail',
    'build_overview',
    'build_overview_section',
    'build_runtime_binding_detail',
    'build_runtime_usage',
    'build_security',
]


def build_security(*, page: int = 1, per_page: int = 5) -> dict[str, Any]:
    """Compatibility projection for callers using the aggregate presentation module."""
    from app.artifact_registry.security.presentation import build_security as build_security_workspace

    return build_security_workspace(page=page, per_page=per_page)
