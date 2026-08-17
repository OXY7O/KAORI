from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_module(name: str, path: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, Path(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_capacity_modules() -> tuple[ModuleType, ModuleType]:
    names = (
        'app.integrations.observability.metrics_source.exceptions',
        'app.integrations.observability.metrics_source.query_profiles',
        'app.metrics_sources.consumer',
        'app.analytics.kubernetes.common.base_service',
        'app.analytics.kubernetes.capacity.evidence',
        'capacity_domain_under_test',
    )
    previous = {name: sys.modules.get(name) for name in names}

    exceptions = ModuleType(names[0])
    exceptions.MetricsSourceError = type('MetricsSourceError', (Exception,), {})  # type: ignore[attr-defined]
    sys.modules[names[0]] = exceptions

    query_profiles = ModuleType(names[1])
    query_profiles.get_kubernetes_query_expression = lambda key: key  # type: ignore[attr-defined]
    sys.modules[names[1]] = query_profiles

    consumer = ModuleType(names[2])
    consumer.MetricsConsumer = object  # type: ignore[attr-defined]
    sys.modules[names[2]] = consumer

    base_service = ModuleType(names[3])
    base_service.bytes_to_gib = lambda value: round(float(value) / (1024**3), 2)  # type: ignore[attr-defined]
    base_service.clamp_percent = lambda value: max(0.0, min(float(value), 100.0))  # type: ignore[attr-defined]
    base_service.raw_percent = lambda value, total: float(value) / float(total) * 100 if total else 0.0  # type: ignore[attr-defined]
    base_service.safe_percent = base_service.raw_percent  # type: ignore[attr-defined]
    base_service.safe_round = lambda value, digits=2: round(float(value), digits)  # type: ignore[attr-defined]
    sys.modules[names[3]] = base_service

    try:
        evidence = _load_module(
            'app.analytics.kubernetes.capacity.evidence',
            'app/analytics/kubernetes/capacity/evidence.py',
        )
        domain = _load_module('capacity_domain_under_test', 'app/analytics/kubernetes/capacity/domain.py')
        return evidence, domain
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def _allocation(evidence: ModuleType, **values: tuple[float, bool]) -> Any:
    scalar = evidence.ScalarEvidence
    return evidence.AllocationEvidence(
        allocatable=scalar(*values['allocatable']),
        requests=scalar(*values['requests']),
        limits=scalar(*values['limits']),
        actual=scalar(*values['actual']),
        peak=scalar(*values['peak']),
    )


def test_capacity_scalar_parser_rejects_missing_and_non_finite_values() -> None:
    evidence, _ = _load_capacity_modules()

    assert evidence._extract_scalar({}) is None
    assert evidence._extract_scalar({'value': [1, 'bad']}) is None
    assert evidence._extract_scalar({'value': [1, 'NaN']}) is None
    assert evidence._extract_scalar({'value': [1, '+Inf']}) is None
    assert evidence._extract_scalar({'value': [1, '12.5']}) == 12.5


def test_capacity_request_overcommit_has_priority_over_limit_and_usage() -> None:
    evidence, domain = _load_capacity_modules()
    allocation = _allocation(
        evidence,
        allocatable=(10, True),
        requests=(11, True),
        limits=(15, True),
        actual=(9.8, True),
        peak=(12, True),
    )

    status = domain.allocation_status('cpu', allocation)

    assert status['label'] == 'CPU Request Overcommit'
    assert status['tone'] == 'critical'


def test_capacity_missing_peak_is_limited_evidence_not_healthy() -> None:
    evidence, domain = _load_capacity_modules()
    allocation = _allocation(
        evidence,
        allocatable=(10, True),
        requests=(4, True),
        limits=(7, True),
        actual=(3, True),
        peak=(0, False),
    )

    status = domain.allocation_status('memory', allocation)

    assert status['label'] == 'Limited Evidence'
    assert status['tone'] == 'unknown'
    assert status['missing_metrics'] == ['peak']


def test_capacity_filesystem_is_reference_and_not_a_scheduling_finding() -> None:
    evidence, domain = _load_capacity_modules()
    scalar = evidence.ScalarEvidence
    capacity = evidence.CapacityEvidence(
        worker_nodes=scalar(3, True),
        ready_worker_nodes=scalar(2, True),
        cpu=_allocation(
            evidence,
            allocatable=(10, True),
            requests=(3, True),
            limits=(6, True),
            actual=(2, True),
            peak=(4, True),
        ),
        memory=_allocation(
            evidence,
            allocatable=(16 * 1024**3, True),
            requests=(4 * 1024**3, True),
            limits=(8 * 1024**3, True),
            actual=(3 * 1024**3, True),
            peak=(5 * 1024**3, True),
        ),
        pod_capacity=scalar(100, True),
        current_pods=scalar(20, True),
        filesystem_capacity=scalar(100 * 1024**3, True),
        filesystem_used=scalar(99 * 1024**3, True),
        filesystem_available=scalar(1 * 1024**3, True),
    )

    summary = domain.build_capacity_summary(capacity)
    allocation = domain.build_allocation_summary(capacity)
    findings = domain.build_governance_findings(summary, allocation)

    assert summary['storage']['scheduling_resource'] is False
    assert summary['storage']['headroom'] == 1.0
    assert all('filesystem' not in item['label'].lower() for item in findings)


def test_capacity_posture_uses_allocation_risk_and_requires_complete_evidence() -> None:
    evidence, domain = _load_capacity_modules()
    scalar = evidence.ScalarEvidence
    capacity = evidence.CapacityEvidence(
        worker_nodes=scalar(3, True),
        ready_worker_nodes=scalar(3, True),
        cpu=_allocation(
            evidence,
            allocatable=(10, True),
            requests=(11, True),
            limits=(12, True),
            actual=(2, True),
            peak=(3, True),
        ),
        memory=_allocation(
            evidence,
            allocatable=(16 * 1024**3, True),
            requests=(4 * 1024**3, True),
            limits=(8 * 1024**3, True),
            actual=(3 * 1024**3, True),
            peak=(5 * 1024**3, True),
        ),
        pod_capacity=scalar(100, True),
        current_pods=scalar(20, True),
        filesystem_capacity=scalar(),
        filesystem_used=scalar(),
        filesystem_available=scalar(),
    )

    summary = domain.build_capacity_summary(capacity)
    allocation = domain.build_allocation_summary(capacity)
    posture = domain.build_capacity_posture(summary, allocation)

    assert posture['label'] == 'Critical'
    assert posture['tone'] == 'critical'
    assert posture['evidence_complete'] is True

    capacity = evidence.CapacityEvidence(
        worker_nodes=capacity.worker_nodes,
        ready_worker_nodes=capacity.ready_worker_nodes,
        cpu=_allocation(
            evidence,
            allocatable=(10, True),
            requests=(4, True),
            limits=(7, True),
            actual=(2, True),
            peak=(3, True),
        ),
        memory=capacity.memory,
        pod_capacity=capacity.pod_capacity,
        current_pods=capacity.current_pods,
        filesystem_capacity=capacity.filesystem_capacity,
        filesystem_used=capacity.filesystem_used,
        filesystem_available=capacity.filesystem_available,
    )
    summary = domain.build_capacity_summary(capacity)
    allocation = domain.build_allocation_summary(capacity)
    posture = domain.build_capacity_posture(summary, allocation)

    assert posture == {
        'label': 'Healthy',
        'tone': 'normal',
        'reason': (
            'Ready-worker allocatable, commitment, current usage, and peak evidence '
            'are complete and remain within the configured envelope.'
        ),
        'evidence_complete': True,
    }


def test_capacity_cluster_info_keeps_worker_and_full_cluster_readiness_separate() -> None:
    evidence, domain = _load_capacity_modules()
    scalar = evidence.ScalarEvidence
    capacity = evidence.CapacityEvidence(
        worker_nodes=scalar(4, True),
        ready_worker_nodes=scalar(3, True),
        cpu=_allocation(
            evidence, allocatable=(1, True), requests=(0, True), limits=(0, True), actual=(0, True), peak=(0, True)
        ),
        memory=_allocation(
            evidence, allocatable=(1, True), requests=(0, True), limits=(0, True), actual=(0, True), peak=(0, True)
        ),
        pod_capacity=scalar(1, True),
        current_pods=scalar(0, True),
        filesystem_capacity=scalar(),
        filesystem_used=scalar(),
        filesystem_available=scalar(),
    )

    info = domain.build_cluster_info(
        capacity,
        kubernetes_version='v1.29.5',
        total_nodes=6,
        ready_nodes=5,
        not_ready_nodes=1,
        control_plane_nodes=2,
    )

    assert info['worker_nodes'] == 4
    assert info['ready_worker_nodes'] == 3
    assert info['not_ready_worker_nodes'] == 1
    assert info['ready_nodes'] == 5
    assert info['not_ready_nodes'] == 1
