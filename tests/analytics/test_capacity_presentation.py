from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_presentation_module() -> ModuleType:
    module_path = Path('app/analytics/common/presentation.py')
    spec = importlib.util.spec_from_file_location('analytics_common_presentation', module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capacity_presenter_backfills_storage_for_legacy_snapshot() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                'cpu': {
                    'capacity': 8,
                    'used': 4,
                    'available': 4,
                    'headroom': 50,
                },
                'memory': {
                    'capacity': 32,
                    'used': 16,
                    'available': 16,
                    'headroom': 50,
                },
                'pods': {
                    'capacity': 110,
                    'used': 55,
                    'available': 55,
                    'headroom': 50,
                },
            }
        }
    )

    storage = context['capacity_summary']['storage']

    assert storage == {
        'capacity': 0,
        'used': 0,
        'available': 0,
        'headroom': 0.0,
        'utilization_percent': 0.0,
    }
    assert context['storage_headroom_display'] == '0.0%'
    assert context['lowest_headroom'] == 50.0
    assert context['lowest_headroom_display'] == '50.0%'


def test_capacity_presenter_marks_missing_capacity_as_zero_utilization() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context({'capacity_summary': {}})

    assert set(context['capacity_summary']) == {'cpu', 'memory', 'pods', 'storage'}
    assert all(
        item['utilization_percent'] == 0.0
        for item in context['capacity_summary'].values()
    )
    assert context['capacity_headroom_available'] is False
    assert context['lowest_headroom_display'] == 'N/A'


def test_capacity_presenter_normalizes_long_float_units() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                'cpu': {
                    'capacity': 12.3456789,
                    'used': 3.14159265,
                    'available': 9.20408625,
                    'headroom': 74.55321987,
                }
            }
        }
    )

    cpu = context['capacity_summary']['cpu']

    assert cpu['capacity'] == 12.35
    assert cpu['used'] == 3.14
    assert cpu['available'] == 9.2
    assert cpu['headroom'] == 74.6
    assert cpu['utilization_percent'] == 25.4
    assert context['cpu_headroom_display'] == '74.6%'
