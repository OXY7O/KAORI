from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_storage_domain_owns_semantic_tones_and_pressure_thresholds() -> None:
    domain = read('app/kubernetes/analytics/storage/domain.py')

    assert "return {'label': 'Critical', 'tone': 'critical'}" in domain
    assert "return {'label': 'Watch', 'tone': 'warning'}" in domain
    assert "return {'label': 'Healthy', 'tone': 'normal'}" in domain
    assert 'if percent >= 90' in domain
    assert 'if percent >= 75' in domain
    assert 'if percent >= 60' not in domain
    assert "'class': 'bg-" not in domain


def test_storage_payload_distinguishes_unavailable_from_zero() -> None:
    payloads = read('app/kubernetes/analytics/common/payloads.py')
    storage_payload = payloads.split('def get_empty_storage_payload', 1)[1].split('def get_empty_workload_payload', 1)[
        0
    ]

    assert "'evidence_available': False" in storage_payload
    assert "'pressure_evidence_available': False" in storage_payload
    assert "'usage_percent': None" in storage_payload
    assert "'capacity': 'N/A'" in storage_payload
    assert "unknown_risk = {'label': 'Unknown', 'tone': 'unknown'}" in storage_payload


def test_storage_pv_summary_uses_factual_provisioning_semantics() -> None:
    domain = read('app/kubernetes/analytics/storage/domain.py')
    capacity = read('app/templates/kubernetes/analytics/storage/partials/_capacity_utilization_panel.html')
    pv_panel = read('app/templates/kubernetes/analytics/storage/partials/_persistent_volumes_panel.html')

    for term in (
        'observed_claim_usage',
        'requested_claim_capacity',
        'unallocated_provisioned_difference',
    ):
        assert term in domain
    assert 'PV Provisioned Capacity Consumption' not in capacity
    assert 'PV Consumed' not in capacity
    assert 'Provisioned Capacity Consumption' not in pv_panel
    assert 'Persistent Volume Provisioning Context' in capacity


def test_storage_recommendations_use_owning_tab_destinations() -> None:
    engine = read('app/intelligence/recommendation_engine.py')
    recommendations = read('app/templates/kubernetes/analytics/storage/partials/_recommendations.html')

    assert "href='/analytics/storage?tab=filesystem'" in engine
    assert "href='/analytics/storage?tab=pvc'" in engine
    assert "href='/analytics/storage?tab=pv'" in engine
    assert "target_tab = 'filesystem'" in recommendations
    assert 'tab=target_tab' in recommendations


def test_storage_empty_payload_defines_partial_pvc_coverage_contract() -> None:
    payloads = read('app/kubernetes/analytics/common/payloads.py')
    storage_payload = payloads.split('def get_empty_storage_payload', 1)[1].split('def get_empty_workload_payload', 1)[
        0
    ]

    for field in (
        'capacity_evidence_complete',
        'used_evidence_complete',
        'pressure_evidence_complete',
        'capacity_observed_count',
        'used_observed_count',
        'pressure_observed_count',
        'evidence_gap_count',
        'pressure_coverage_display',
        'pressure_capacity',
        'pressure_used',
        'pressure_free',
        'observed_claim_usage_evidence_complete',
        'observed_claim_usage_count',
        'observed_claim_usage_gap_count',
        'observed_claim_usage_coverage_display',
    ):
        assert f"'{field}'" in storage_payload
