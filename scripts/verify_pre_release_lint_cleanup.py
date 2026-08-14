#!/usr/bin/env python3
"""Guard semantic lint fixes from the 2026-08 pre-release cleanup."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(relative: str, needle: str, errors: list[str]) -> None:
    if needle not in read(relative):
        errors.append(f'{relative}: missing {needle!r}')


def forbid(relative: str, needle: str, errors: list[str]) -> None:
    if needle in read(relative):
        errors.append(f'{relative}: obsolete lint fingerprint remains: {needle!r}')


def main() -> int:
    errors: list[str] = []

    for relative, symbol in (
        ('app/analytics/kubernetes/alerts/signals.py', 'load_alerts_by_source'),
        ('app/analytics/kubernetes/forecast/calculation.py', 'as_dict as _as_dict'),
        ('app/analytics/kubernetes/forecast/calculation.py', 'as_list as _as_list'),
        ('app/analytics/kubernetes/forecast/calculation.py', 'safe_float as _safe_float'),
        ('app/analytics/kubernetes/forecast/calculation.py', 'safe_int as _safe_int'),
        ('app/cluster/quick_sync.py', 'build_cluster_sync_snapshot'),
        ('app/inventory/kubernetes/routes.py', 'build_cluster_context'),
        ('app/jobs/registry.py', 'job_operation_label'),
        ('app/notifications/queries.py', 'event_label'),
        ('tests/contracts/reports/test_single_pdf_engine_contract.py', 'import ast'),
    ):
        forbid(relative, symbol, errors)

    for relative, forbidden_import in (
        ('app/analytics/kubernetes/alerts/application.py', 'from typing import Any, Mapping'),
        ('app/analytics/kubernetes/alerts/records.py', 'from typing import Any, Iterable'),
        ('app/analytics/kubernetes/capacity/domain.py', 'from typing import Any, Callable'),
        ('app/analytics/kubernetes/storage/domain.py', 'from typing import Any, Iterable'),
        ('app/analytics/kubernetes/top_consumers/rows.py', 'from typing import Any, Callable'),
        ('app/common/provider_query_runtime.py', 'from typing import Any, Iterator'),
        ('app/governance/tls_certificates/collector.py', 'from typing import Any, Callable'),
    ):
        forbid(relative, forbidden_import, errors)

    contracts = 'app/analytics/kubernetes/alerts/contracts.py'
    for name in (
        'AlertSourceHealthSummary',
        'AlertRoutingSummary',
        'AlertSilenceSummary',
        'AlertInhibitionSummary',
        'AlertOwnershipSummary',
        'AlertIncidentReadinessSummary',
    ):
        require(contracts, f'class {name}(TypedDict):', errors)
        forbid(contracts, f'{name} = TypedDict(', errors)
    require(contracts, 'type AlertLoadResult =', errors)
    require(contracts, 'def paginate_items[ItemT](', errors)

    require('app/common/http.py', 'type HeaderSource =', errors)
    require('app/common/pagination.py', 'def paginate_sequence[ItemT](', errors)
    require('app/integrations/consumer/contracts.py', 'class ConsumerResult[PayloadT]:', errors)
    require('app/kubernetes_operations/operation_flow.py', 'def validate_then_apply[ResultT](', errors)

    for relative in (
        'app/analytics/kubernetes/materialization/requests.py',
        'app/analytics/kubernetes/top_consumers/evidence.py',
    ):
        forbid(relative, '= lambda ', errors)

    for relative, token in (
        ('app/analytics/kubernetes/utilization/service.py', 'from app.integrations.prometheus.exceptions import PrometheusError'),
        (
            'app/kubernetes_operations/secrets/reveal_service.py',
            'from app.common.kubernetes_secrets import scrub_mapping_values, scrub_secret_payload',
        ),
        ('app/common/sensitive_uploads.py', 'def decode_utf8('),
    ):
        require(relative, token, errors)

    for relative, token in (
        ('app/analytics/kubernetes/workload/quota.py', "cpu_limit = resources['limits.cpu']"),
        ('app/analytics/kubernetes/workload/quota.py', "cpu_request = resources['requests.cpu']"),
        ('app/analytics/kubernetes/workload/quota.py', "memory_limit = resources['limits.memory']"),
        ('app/analytics/kubernetes/workload/quota.py', "memory_request = resources['requests.memory']"),
        (
            'tests/contracts/kubernetes/test_kubernetes_operations_configmap_secret_styling_contract.py',
            "catalog = read('app/templates/components/operational_workflow_catalog.html')",
        ),
    ):
        require(relative, token, errors)

    for relative, token in (
        (
            'tests/contracts/access/test_identity_provider_refinement_contract.py',
            "script = read('app/static/js/identity_provider_form.js')",
        ),
        (
            'tests/contracts/kubernetes/test_service_inventory_title_case_and_detail_contract.py',
            "service = read('app/inventory/kubernetes/resources/services.py')",
        ),
    ):
        forbid(relative, token, errors)

    for relative, token in (
        (
            'app/alertmanager/bindings.py',
            'from __future__ import annotations\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/alertmanager/service.py',
            'from urllib.parse import urlsplit\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/integrations/alertmanager/binding_management.py',
            'from __future__ import annotations\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/integrations/alertmanager/binding_validation.py',
            'from typing import Any\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/integrations/prometheus/binding_management.py',
            'from __future__ import annotations\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/integrations/prometheus/binding_validation.py',
            'from typing import Any\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
        (
            'app/prometheus/service.py',
            'from urllib.parse import urlsplit\n\nfrom sqlalchemy.exc import SQLAlchemyError',
        ),
    ):
        require(relative, token, errors)

    job_verifier = read('scripts/verify_report_job_standard.py')
    if '; continue' in job_verifier or 'if token not in text: errors.append' in job_verifier:
        errors.append('scripts/verify_report_job_standard.py: compact multi-statement lint debt remains')

    forbid(
        'tests/contracts/analytics/test_top_consumers_workspace_presentation_contract.py',
        "assert f'data-consumer-category=",
        errors,
    )
    require(
        'tests/kubernetes_operations/test_configmap_validation_contract.py',
        "len(b'binary.bin') + len(b'hello')",
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print('KAORI pre-release semantic lint cleanup contract passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
