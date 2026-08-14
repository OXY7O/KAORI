from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_object_storage_vector_parsing_supports_scalar_and_bucket_labels() -> None:
    parsing = load_module('object_storage_parsing_under_test', 'app/analytics/object_storage/parsing.py')
    payload = {
        'data': {
            'result': [
                {'metric': {'bucket': 'archive'}, 'value': [1_700_000_000, '2048']},
                {'metric': {'bucket': 'reports'}, 'value': [1_700_000_000, '4096']},
            ]
        }
    }

    assert parsing.vector_scalar(payload) == 2048.0
    assert parsing.vector_by_label(payload, 'bucket') == {'archive': 2048.0, 'reports': 4096.0}


def test_object_storage_matrix_parser_keeps_timestamp_aligned_values() -> None:
    parsing = load_module('object_storage_parsing_matrix_under_test', 'app/analytics/object_storage/parsing.py')
    payload = {'data': {'result': [{'metric': {}, 'values': [[100, '10'], [200, '20.5']]}]}}

    assert parsing.matrix_points(payload) == [
        {'timestamp': 100.0, 'value': 10.0},
        {'timestamp': 200.0, 'value': 20.5},
    ]


def test_object_storage_forecast_projects_growth_without_claiming_capacity_eta_on_decline() -> None:
    forecasting = load_module('object_storage_forecasting_under_test', 'app/analytics/object_storage/forecasting.py')
    growing = forecasting.linear_forecast(
        [
            {'timestamp': 0.0, 'value': 100.0},
            {'timestamp': 86_400.0, 'value': 200.0},
        ],
        capacity_bytes=1000.0,
    )
    declining = forecasting.linear_forecast(
        [
            {'timestamp': 0.0, 'value': 200.0},
            {'timestamp': 86_400.0, 'value': 100.0},
        ],
        capacity_bytes=1000.0,
    )

    assert growing['growth_per_day'] == 100.0
    assert growing['projected_7d'] == 900.0
    assert growing['days_to_capacity'] == 8.0
    assert declining['growth_per_day'] == -100.0
    assert declining['days_to_capacity'] is None


def test_object_storage_capacity_presentation_uses_kaori_thresholds() -> None:
    presentation = load_module('object_storage_presentation_under_test', 'app/analytics/object_storage/presentation.py')

    assert presentation.format_bytes(1024) == '1.0 KiB'
    assert presentation.utilization_percent(850, 1000) == 85.0
    assert presentation.utilization_tone(84.9) == 'normal'
    assert presentation.utilization_tone(85.0) == 'warning'
    assert presentation.utilization_tone(95.0) == 'critical'
