from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load_engine():
    spec = importlib.util.spec_from_file_location(
        'alerts_recommendation_engine_under_test',
        ROOT / 'app/intelligence/recommendation_engine.py',
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_partial_anomaly_evidence_produces_recovery_recommendation() -> None:
    engine = _load_engine()

    recommendations = engine.build_alerts_actionable_recommendations(
        {
            'all_alerts': [],
            'all_anomalies': [],
            'source_status': {'connected': True},
            'anomaly_source_status': {
                'connected': True,
                'partial': True,
                'failed_queries': ['readiness'],
            },
            'collection_warnings': [{'title': 'Partial evidence'}],
            'selected_cluster_signal_overview': {
                'priority': {'label': 'Limited Evidence'}
            },
        }
    )

    titles = [item['title'] for item in recommendations]
    assert 'Restore Complete Anomaly Evidence' in titles
    assert 'No Active Alert or Anomaly Action Required' not in titles


def test_complete_empty_evidence_uses_non_actionable_monitoring_baseline() -> None:
    engine = _load_engine()

    recommendations = engine.build_alerts_actionable_recommendations(
        {
            'all_alerts': [],
            'all_anomalies': [],
            'source_status': {'connected': True},
            'anomaly_source_status': {'connected': True, 'partial': False},
            'collection_warnings': [],
            'selected_cluster_signal_overview': {
                'priority': {
                    'label': 'Normal',
                    'description': 'No active signal requires review.',
                }
            },
        }
    )

    assert recommendations[0]['title'] == 'No Active Alert or Anomaly Action Required'
    assert recommendations[0]['is_actionable'] == 'No'
