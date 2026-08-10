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
        'app/analytics/utilization/service.py',
        'from app.integrations.prometheus.exceptions import PrometheusError',
        'canonical PrometheusError import',
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
        'app/analytics/top_consumers/domain.py',
        '-> TypeGuard[dict[str, Any]]:',
        'Top Consumers payload type guard',
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

    print('KAORI pre-release type-safety contract passed.')


if __name__ == '__main__':
    main()
