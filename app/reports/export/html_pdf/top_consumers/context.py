from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypedDict, Unpack


class _ContextMetadata(TypedDict):
    report_id: str
    report_name: str
    cluster_scope: str
    namespace_scope: str
    period_label: str
    data_cutoff: str
    generated_at: str
    generated_by: str
    classification: str


@dataclass(frozen=True, slots=True)
class TopConsumersContext:
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


def build_top_consumers_context(
    report: Any,
    payload: Mapping[str, Any],
    **metadata: Unpack[_ContextMetadata],
) -> TopConsumersContext:
    return TopConsumersContext(report=report, payload=payload, **metadata)
