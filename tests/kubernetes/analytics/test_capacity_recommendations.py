from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_recommendation_module() -> ModuleType:
    module_path = Path('app/intelligence/recommendation_engine.py')
    spec = importlib.util.spec_from_file_location('capacity_recommendation_engine', module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capacity_cards_can_omit_presentation_classes() -> None:
    engine = _load_recommendation_module()

    cards = engine.format_recommendation_cards(
        [
            {
                'title': 'Review CPU headroom',
                'description': 'CPU headroom is constrained.',
                'priority': 'Warning',
                'source': 'capacity_risk',
                'resource': 'cpu',
            }
        ],
        include_presentation_classes=False,
    )

    assert cards[0]['icon'] == 'cpu'
    assert cards[0]['priority'] == 'Warning'
    assert 'icon_class' not in cards[0]
    assert 'priority_class' not in cards[0]


def test_capacity_recommendations_skip_unavailable_denominators() -> None:
    engine = _load_recommendation_module()

    recommendations = engine.build_capacity_actionable_recommendations(
        {
            'risk_summary': [
                {
                    'resource': 'storage',
                    'label': 'Storage',
                    'headroom': 0,
                    'evidence_available': False,
                    'status': {'label': 'Critical', 'tone': 'critical'},
                }
            ],
            'capacity_summary': {
                'storage': {
                    'capacity': 0,
                    'headroom': 0,
                    'evidence_available': False,
                }
            },
            'governance_findings': [],
        }
    )

    assert {item['source'] for item in recommendations} == {
        'capacity_baseline',
        'capacity_practice',
    }
    assert all(item['is_actionable'] == 'No' for item in recommendations)
    assert all(item['source'] not in {'capacity_risk', 'capacity_headroom'} for item in recommendations)
