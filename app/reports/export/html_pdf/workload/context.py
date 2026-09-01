from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkloadContext:
    report: Any
    payload: Mapping[str, Any]
    report_id: str
    report_name: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    data_cutoff: str
    generated_at: str
    generated_by: str
    classification: str


def build_workload_context(
    report: Any,
    payload: Mapping[str, Any],
    *,
    report_id: str,
    report_name: str,
    cluster_scope: str,
    namespace_scope: str,
    period_label: str,
    data_cutoff: str,
    generated_at: str,
    generated_by: str,
    classification: str,
) -> WorkloadContext:
    return WorkloadContext(
        report=report,
        payload=payload,
        report_id=report_id,
        report_name=report_name,
        cluster_scope=cluster_scope,
        namespace_scope=namespace_scope,
        period_label=period_label,
        data_cutoff=data_cutoff,
        generated_at=generated_at,
        generated_by=generated_by,
        classification=classification,
    )
