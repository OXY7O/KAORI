#!/usr/bin/env python3
"""Guard durable type-safety boundaries found during the pre-release audit."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def _require(relative_path: str, needle: str, description: str) -> None:
    if needle not in _read(relative_path):
        raise SystemExit(f'{relative_path}: missing {description}.')


def _forbid(relative_path: str, needle: str, description: str) -> None:
    if needle in _read(relative_path):
        raise SystemExit(f'{relative_path}: {description}.')


def main() -> None:
    _require(
        'app/analytics/kubernetes/utilization/service.py',
        'from app.integrations.observability.metrics_source.exceptions import MetricsSourceError',
        'canonical MetricsSourceError import',
    )
    _require(
        'app/kubernetes_operations/secrets/reveal_service.py',
        'from app.common.kubernetes_secrets import scrub_mapping_values, scrub_secret_payload',
        'secret scrubber imports',
    )
    _require(
        'app/common/dependencies.py',
        'class ClusterIdentity(Protocol):',
        'minimal cluster dependency protocol',
    )
    _require(
        'app/analytics/kubernetes/top_consumers/domain.py',
        '-> TypeGuard[dict[str, Any]]:',
        'Top Consumers payload type guard',
    )
    _require(
        'app/common/dependencies.py',
        'def name(self) -> object: ...',
        'ORM-compatible cluster display-name protocol',
    )
    for needle, description in (
        ('actionable_recommendations = [', 'forecast recommendation normalization'),
        (
            "_as_list(forecast_payload.get('actionable_recommendations'))",
            'forecast recommendation list boundary',
        ),
        ('if isinstance(item, dict)', 'forecast recommendation mapping guard'),
        (
            "'recommendation_count': count_actionable_recommendations(actionable_recommendations)",
            'forecast normalized recommendation consumption',
        ),
    ):
        _require('app/analytics/kubernetes/forecast/presentation.py', needle, description)
    _forbid(
        'app/analytics/kubernetes/forecast/presentation.py',
        "count_actionable_recommendations(\n            forecast_payload.get('actionable_recommendations')",
        'forecast snapshot recommendation count bypasses normalized boundary',
    )
    _require(
        'app/analytics/kubernetes/overview/snapshot_summary.py',
        'snapshots: Sequence[Any],',
        'sequence-compatible snapshot summary boundary',
    )
    _require(
        'app/dashboards/kubernetes/service.py',
        '_cluster_health_rows, pagination = paginate_sequence(',
        'dashboard pagination result separation',
    )
    _require(
        'app/reports/export/html_pdf/forecast_analysis.py',
        'projected is not None and projected >= _CRITICAL_THRESHOLD',
        'forecast PDF optional projection guard',
    )
    _require(
        'app/reports/export/xlsx/style.py',
        'footer = sheet.oddFooter',
        'optional OpenPyXL footer guard',
    )
    _require(
        'app/reports/schedules/service.py',
        'if dispatch_job is None:',
        'optional scheduled report dispatch-job guard',
    )
    _require(
        'app/integrations/runtime/recovery.py',
        'class RecoveryDispatchResult(TypedDict):',
        'typed recovery dispatch result',
    )
    _forbid(
        'app/reports/storage/service.py',
        '_get_current_object()',
        'private Flask LocalProxy access remains in report storage cache code',
    )
    _forbid(
        'app/jobs/policies/service.py',
        'return JobPolicy(',
        'JobPolicy still relies on untyped declarative constructor kwargs',
    )
    _require(
        'app/reports/export/xlsx/style.py',
        'sheet.page_setup = PrintPageSetup(',
        'explicit OpenPyXL page setup construction',
    )

    print('PASS — KAORI Type Safety')


if __name__ == '__main__':
    main()
