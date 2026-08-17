from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class VectorEvidence:
    rows: tuple[dict[str, Any], ...] = ()
    observed: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StorageEvidence:
    namespaces: VectorEvidence
    filesystem_var_size: VectorEvidence
    filesystem_var_available: VectorEvidence
    filesystem_root_size: VectorEvidence
    filesystem_root_available: VectorEvidence
    pvc_requested: VectorEvidence
    pvc_capacity: VectorEvidence
    pvc_used: VectorEvidence
    pvc_available: VectorEvidence
    pvc_status: VectorEvidence
    pvc_info: VectorEvidence
    pv_capacity: VectorEvidence
    pv_status: VectorEvidence
    pv_info: VectorEvidence


def _sample(metric: dict[str, str], value: float) -> dict[str, Any]:
    return {'metric': metric, 'value': [0, str(value)]}


def _load_domain() -> ModuleType:
    package_names = ('app', 'app.analytics', 'app.kubernetes.analytics.common', 'app.kubernetes.analytics.storage')
    original = {name: sys.modules.get(name) for name in package_names}
    module_names = (
        'app.kubernetes.analytics.common.base_service',
        'app.kubernetes.analytics.storage.evidence',
        'app.kubernetes.analytics.storage.parsing',
        'app.kubernetes.analytics.storage.domain',
    )
    original_modules = {name: sys.modules.get(name) for name in module_names}
    try:
        for name in package_names:
            package = ModuleType(name)
            package.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = package

        base = ModuleType('app.kubernetes.analytics.common.base_service')
        base.raw_percent = lambda value, total: value / total * 100 if total else 0
        base.safe_round = round
        sys.modules[base.__name__] = base

        evidence = ModuleType('app.kubernetes.analytics.storage.evidence')
        evidence.VectorEvidence = VectorEvidence
        evidence.StorageEvidence = StorageEvidence
        evidence.sample_metric = lambda item: item.get('metric', {})
        evidence.sample_value = lambda item: float(item['value'][1])
        sys.modules[evidence.__name__] = evidence

        parsing = _load_file(
            'app.kubernetes.analytics.storage.parsing',
            ROOT / 'app/kubernetes/analytics/storage/parsing.py',
        )
        sys.modules[parsing.__name__] = parsing
        return _load_file(
            'app.kubernetes.analytics.storage.domain',
            ROOT / 'app/kubernetes/analytics/storage/domain.py',
        )
    finally:
        for name, value in {**original, **original_modules}.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def _load_file(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _evidence(**overrides: VectorEvidence) -> StorageEvidence:
    empty = VectorEvidence()
    values = {field: empty for field in StorageEvidence.__dataclass_fields__}
    values.update(overrides)
    return StorageEvidence(**values)


def test_filesystem_uses_complete_root_pair_when_var_is_incomplete() -> None:
    domain = _load_domain()
    evidence = _evidence(
        filesystem_var_size=VectorEvidence((_sample({'node': 'worker-1'}, 100),), observed=True),
        filesystem_root_size=VectorEvidence((_sample({'node': 'worker-1'}, 200),), observed=True),
        filesystem_root_available=VectorEvidence((_sample({'node': 'worker-1'}, 100),), observed=True),
    )

    row = domain.build_filesystem_rows(evidence)[0]

    assert row['mountpoint'] == '/'
    assert row['usage_percent'] == 50.0
    assert row['evidence_available'] is True


def test_filesystem_missing_available_bytes_remains_unknown() -> None:
    domain = _load_domain()
    evidence = _evidence(filesystem_var_size=VectorEvidence((_sample({'node': 'worker-1'}, 100),), observed=True))

    row = domain.build_filesystem_rows(evidence)[0]

    assert row['usage_percent'] is None
    assert row['evidence_available'] is False
    assert row['risk'] == {'label': 'Unknown', 'tone': 'unknown'}


def test_pvc_pressure_uses_observed_capacity_not_requested_capacity() -> None:
    domain = _load_domain()
    labels = {'namespace': 'team-a', 'persistentvolumeclaim': 'data'}
    evidence = _evidence(
        pvc_requested=VectorEvidence((_sample(labels, 200),), observed=True),
        pvc_capacity=VectorEvidence((_sample(labels, 100),), observed=True),
        pvc_used=VectorEvidence((_sample(labels, 80),), observed=True),
        pvc_available=VectorEvidence((_sample(labels, 20),), observed=True),
        pvc_status=VectorEvidence((_sample({**labels, 'phase': 'Bound'}, 1),), observed=True),
        pvc_info=VectorEvidence((_sample(labels, 1),), observed=True),
    )

    row = domain.build_pvc_rows(evidence)[0]

    assert row['usage_percent'] == 80.0
    assert row['risk'] == {'label': 'Watch', 'tone': 'warning'}
    assert row['requested_bytes'] == 200
    assert row['capacity_bytes'] == 100


def test_lost_pvc_sets_critical_storage_posture_without_pressure_evidence() -> None:
    domain = _load_domain()
    labels = {'namespace': 'team-a', 'persistentvolumeclaim': 'data'}
    evidence = _evidence(
        pvc_status=VectorEvidence((_sample({**labels, 'phase': 'Lost'}, 1),), observed=True),
        pvc_info=VectorEvidence((_sample(labels, 1),), observed=True),
    )

    payload = domain.build_storage_payload(evidence)

    assert payload['storage_summary']['persistent_storage']['pvc_rows'][0]['risk'] == {
        'label': 'Critical',
        'tone': 'critical',
    }
    assert payload['storage_posture']['label'] == 'Critical'


def test_unknown_pvc_lifecycle_is_not_classified_healthy() -> None:
    domain = _load_domain()

    risk = domain.pvc_risk(
        'Unknown',
        20.0,
        pressure_available=True,
    )

    assert risk == {'label': 'Unknown', 'tone': 'unknown'}


def test_critical_pvc_pressure_is_not_masked_by_pending_lifecycle() -> None:
    domain = _load_domain()

    risk = domain.pvc_risk(
        'Pending',
        95.0,
        pressure_available=True,
    )

    assert risk == {'label': 'Critical', 'tone': 'critical'}


def test_materialized_pv_summary_uses_collected_claim_evidence() -> None:
    domain = _load_domain()
    claim_labels = {'namespace': 'team-a', 'persistentvolumeclaim': 'data'}
    volume_labels = {'persistentvolume': 'pv-data'}
    evidence = _evidence(
        pvc_requested=VectorEvidence((_sample(claim_labels, 80),), observed=True),
        pvc_capacity=VectorEvidence((_sample(claim_labels, 100),), observed=True),
        pvc_used=VectorEvidence((_sample(claim_labels, 40),), observed=True),
        pvc_available=VectorEvidence((_sample(claim_labels, 60),), observed=True),
        pvc_status=VectorEvidence((_sample({**claim_labels, 'phase': 'Bound'}, 1),), observed=True),
        pvc_info=VectorEvidence(
            (_sample({**claim_labels, 'volumename': 'pv-data'}, 1),),
            observed=True,
        ),
        pv_capacity=VectorEvidence((_sample(volume_labels, 100),), observed=True),
        pv_status=VectorEvidence((_sample({**volume_labels, 'phase': 'Bound'}, 1),), observed=True),
        pv_info=VectorEvidence((_sample(volume_labels, 1),), observed=True),
    )

    summary = domain.build_storage_payload(evidence)['storage_summary']['persistent_storage']['pv']

    assert summary['requested_claim_capacity'] == '80 B'
    assert summary['observed_claim_usage'] == '40 B'
    assert summary['unallocated_provisioned_difference'] == '20 B'


def test_observed_empty_inventory_is_zero_not_unavailable() -> None:
    domain = _load_domain()

    pvc = domain.summarize_pvc([], inventory_observed=True, status_observed=True, scope_label='All Namespaces')
    pv = domain.summarize_pv(
        [],
        inventory_observed=True,
        status_observed=True,
        claim_inventory_observed=True,
    )

    assert pvc['count_display'] == '0'
    assert pvc['evidence_complete'] is True
    assert pvc['risk']['label'] == 'No Claims'
    assert pv['count_display'] == '0'
    assert pv['evidence_complete'] is True
    assert pv['risk']['label'] == 'No Volumes'


def test_incomplete_domains_are_not_classified_healthy() -> None:
    domain = _load_domain()
    posture = domain.build_storage_posture(
        {'query_observed': True, 'evidence_complete': False, 'risk': {'tone': 'unknown'}},
        {'inventory_evidence_available': True, 'evidence_complete': False, 'risk': {'tone': 'unknown'}},
        {'inventory_evidence_available': False, 'evidence_complete': False, 'risk': {'tone': 'unknown'}},
    )

    assert posture['label'] == 'Limited Evidence'
    assert posture['tone'] == 'unknown'


def test_pvc_summary_preserves_partial_capacity_and_usage_aggregates() -> None:
    domain = _load_domain()
    rows = [
        {
            'status': 'Bound',
            'requested_bytes': 100.0,
            'capacity_bytes': 100.0,
            'used_bytes': 40.0,
            'free_bytes': 60.0,
            'risk': {'label': 'Healthy', 'tone': 'normal'},
        },
        {
            'status': 'Bound',
            'requested_bytes': 200.0,
            'capacity_bytes': 200.0,
            'used_bytes': 60.0,
            'free_bytes': 140.0,
            'risk': {'label': 'Healthy', 'tone': 'normal'},
        },
        {
            'status': 'Bound',
            'requested_bytes': 300.0,
            'capacity_bytes': None,
            'used_bytes': None,
            'free_bytes': None,
            'risk': {'label': 'Unknown', 'tone': 'unknown'},
        },
    ]

    summary = domain.summarize_pvc(
        rows,
        inventory_observed=True,
        status_observed=True,
        scope_label='All Namespaces',
    )

    assert summary['capacity'] == '300 B'
    assert summary['used'] == '100 B'
    assert summary['pressure_capacity'] == '300 B'
    assert summary['pressure_used'] == '100 B'
    assert summary['pressure_free'] == '200 B'
    assert summary['used_percent'] == 33.3
    assert summary['capacity_evidence_available'] is True
    assert summary['used_evidence_available'] is True
    assert summary['pressure_evidence_available'] is True
    assert summary['capacity_evidence_complete'] is False
    assert summary['used_evidence_complete'] is False
    assert summary['pressure_evidence_complete'] is False
    assert summary['capacity_observed_count'] == 2
    assert summary['used_observed_count'] == 2
    assert summary['pressure_observed_count'] == 2
    assert summary['pressure_coverage_display'] == '2 of 3 PVC'
    assert summary['pressure_coverage_percent'] == 66.7
    assert summary['evidence_gap_count'] == 1
    assert summary['risk'] == {'label': 'Limited Evidence', 'tone': 'unknown'}


def test_pvc_pressure_uses_only_rows_with_paired_capacity_and_usage() -> None:
    domain = _load_domain()
    rows = [
        {
            'status': 'Bound',
            'requested_bytes': 100.0,
            'capacity_bytes': 100.0,
            'used_bytes': 50.0,
            'free_bytes': 50.0,
            'risk': {'label': 'Healthy', 'tone': 'normal'},
        },
        {
            'status': 'Bound',
            'requested_bytes': 200.0,
            'capacity_bytes': 200.0,
            'used_bytes': None,
            'free_bytes': None,
            'risk': {'label': 'Unknown', 'tone': 'unknown'},
        },
        {
            'status': 'Bound',
            'requested_bytes': 300.0,
            'capacity_bytes': None,
            'used_bytes': 70.0,
            'free_bytes': None,
            'risk': {'label': 'Unknown', 'tone': 'unknown'},
        },
    ]

    summary = domain.summarize_pvc(
        rows,
        inventory_observed=True,
        status_observed=True,
        scope_label='All Namespaces',
    )

    assert summary['capacity'] == '300 B'
    assert summary['used'] == '120 B'
    assert summary['pressure_capacity'] == '100 B'
    assert summary['pressure_used'] == '50 B'
    assert summary['used_percent'] == 50.0
    assert summary['capacity_coverage_display'] == '2 of 3 PVC'
    assert summary['used_coverage_display'] == '2 of 3 PVC'
    assert summary['pressure_coverage_display'] == '1 of 3 PVC'


def test_unobserved_empty_pvc_scope_remains_unknown() -> None:
    domain = _load_domain()

    summary = domain.summarize_pvc(
        [],
        inventory_observed=False,
        status_observed=False,
        scope_label='All Namespaces',
    )

    assert summary['risk'] == {'label': 'Unknown', 'tone': 'unknown'}
    assert summary['capacity'] == 'N/A'
    assert summary['used'] == 'N/A'
    assert summary['pressure_coverage_display'] == 'N/A'


def test_pv_summary_preserves_partial_observed_claim_usage() -> None:
    domain = _load_domain()
    pv_rows = [
        {
            'status': 'Bound',
            'capacity_bytes': 600.0,
            'risk': {'label': 'Healthy', 'tone': 'normal'},
        },
    ]
    claim_rows = [
        {'requested_bytes': 100.0, 'used_bytes': 40.0},
        {'requested_bytes': 200.0, 'used_bytes': 60.0},
        {'requested_bytes': 300.0, 'used_bytes': None},
    ]

    summary = domain.summarize_pv(
        pv_rows,
        inventory_observed=True,
        status_observed=True,
        claim_rows=claim_rows,
        claim_inventory_observed=True,
    )

    assert summary['capacity'] == '600 B'
    assert summary['requested_claim_capacity'] == '600 B'
    assert summary['observed_claim_usage'] == '100 B'
    assert summary['observed_claim_usage_evidence_available'] is True
    assert summary['observed_claim_usage_evidence_complete'] is False
    assert summary['observed_claim_usage_count'] == 2
    assert summary['total_claim_count'] == 3
    assert summary['observed_claim_usage_gap_count'] == 1
    assert summary['observed_claim_usage_coverage_display'] == '2 of 3 PVC'
    assert summary['observed_claim_usage_coverage_percent'] == 66.7
    assert summary['claim_usage_vs_provisioned_percent'] is None
    assert summary['unallocated_provisioned_difference'] == '0 B'
