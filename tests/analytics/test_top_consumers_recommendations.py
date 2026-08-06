from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumer_recommendations_open_canonical_tabs() -> None:
    source = read('app/analytics/top_consumers/recommendations.py')

    for target in (
        '/analytics/top-consumers?tab=records&focus=missing_requests',
        '/analytics/top-consumers?tab=records&focus=high_usage',
        '/analytics/top-consumers?tab=records&resource=pvc&focus=high_pvc',
        '/analytics/top-consumers?tab=rankings',
        '/analytics/top-consumers?tab=recommendations',
    ):
        assert target in source


def test_dominant_namespace_scoring_uses_contribution_not_retired_usage_percent() -> None:
    source = read('app/analytics/top_consumers/recommendations.py')
    helper = source.split('def get_top_consumer_dominant_namespaces', 1)[1]

    assert "row.get('contribution_percent', 0)" in helper
    assert "row.get('usage_percent', 0)" not in helper


def test_recommendations_require_confirmed_configuration_evidence() -> None:
    source = read('app/analytics/top_consumers/recommendations.py')

    assert "row.get('request_evidence_available') is True" in source
    assert "row.get('limit_evidence_available') is True" in source
    assert 'at least 80% of observed' in source
    assert 'volume capacity.' in source
