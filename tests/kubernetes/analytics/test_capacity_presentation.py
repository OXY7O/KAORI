from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _percent_display(value: Any, *, digits: int = 1) -> str:
    if value is None:
        return 'N/A'
    return f'{float(value):.{digits}f}%'


def _load_presentation_module() -> ModuleType:
    dependency_name = 'app.kubernetes.analytics.common.presentation'
    dependency = ModuleType(dependency_name)
    dependency.percent_display = _percent_display  # type: ignore[attr-defined]
    previous = sys.modules.get(dependency_name)
    sys.modules[dependency_name] = dependency
    try:
        module_path = Path('app/kubernetes/analytics/capacity/presentation.py')
        spec = importlib.util.spec_from_file_location('capacity_presentation_under_test', module_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop(dependency_name, None)
        else:
            sys.modules[dependency_name] = previous


def test_capacity_presenter_marks_missing_storage_as_unavailable() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                'cpu': {'capacity': 8, 'used': 4, 'available': 4, 'headroom': 50},
                'memory': {'capacity': 32, 'used': 16, 'available': 16, 'headroom': 50},
                'pods': {'capacity': 110, 'used': 55, 'available': 55, 'headroom': 50},
            }
        }
    )

    storage = context['capacity_summary']['storage']

    assert storage == {
        'capacity_evidence_available': False,
        'usage_evidence_available': False,
        'evidence_available': False,
        'scheduling_resource': False,
        'scope_label': 'Operational node-filesystem reference; not Kubernetes allocatable capacity',
        'capacity': None,
        'used': None,
        'available': None,
        'headroom': None,
        'utilization_percent': None,
        'status_label': 'Unknown',
        'tone': 'unknown',
    }
    assert context['storage_headroom_display'] == 'N/A'
    assert context['lowest_headroom'] == 50.0
    assert context['lowest_headroom_display'] == '50.0%'
    assert context['lowest_headroom_metric_display'] == 'CPU · 50.0%'
    assert context['capacity_scheduling_evidence_complete'] is False
    assert context['capacity_posture']['label'] == 'Limited Evidence'
    assert context['capacity_posture']['tone'] == 'unknown'


def test_capacity_presenter_uses_unknown_and_na_for_missing_capacity() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context({'capacity_summary': {}})

    assert set(context['capacity_summary']) == {'cpu', 'memory', 'pods', 'storage'}
    assert all(item['utilization_percent'] is None for item in context['capacity_summary'].values())
    assert all(item['headroom'] is None for item in context['capacity_summary'].values())
    assert all(item['status_label'] == 'Unknown' for item in context['capacity_summary'].values())
    assert context['capacity_headroom_available'] is False
    assert context['capacity_scheduling_evidence_complete'] is False
    assert context['capacity_scheduling_evidence_partial'] is False
    assert context['lowest_headroom'] is None
    assert context['lowest_headroom_display'] == 'N/A'
    assert context['lowest_headroom_metric_display'] == 'N/A'
    assert context['capacity_posture']['label'] == 'Unknown'
    assert context['capacity_posture']['tone'] == 'unknown'


def test_capacity_presenter_normalizes_long_float_units_and_identifies_bottleneck() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                'cpu': {
                    'capacity': 12.3456789,
                    'used': 3.14159265,
                    'available': 9.20408625,
                    'headroom': 74.55321987,
                },
                'memory': {
                    'capacity': 32,
                    'used': 24,
                    'available': 8,
                    'headroom': 25,
                },
            }
        }
    )

    cpu = context['capacity_summary']['cpu']
    memory = context['capacity_summary']['memory']

    assert cpu['capacity'] == 12.35
    assert cpu['used'] == 3.14
    assert cpu['available'] == 9.2
    assert cpu['headroom'] == 74.6
    assert cpu['utilization_percent'] == 25.4
    assert cpu['tone'] == 'normal'
    assert memory['tone'] == 'warning'
    assert context['cpu_headroom_display'] == '74.6%'
    assert context['lowest_headroom_resource'] == 'memory'
    assert context['lowest_headroom_metric_display'] == 'Memory · 25.0%'
    assert context['capacity_posture']['label'] == 'Limited Evidence'
    assert context['capacity_posture']['tone'] == 'unknown'


def test_capacity_presenter_marks_healthy_only_when_all_scheduling_evidence_is_complete() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                resource: {'capacity': 100, 'used': 20, 'available': 80, 'headroom': 80}
                for resource in ('cpu', 'memory', 'pods')
            },
            'allocation_summary': {resource: {'complete': True} for resource in ('cpu', 'memory', 'pods')},
        }
    )

    assert context['capacity_scheduling_evidence_complete'] is True
    assert context['capacity_scheduling_evidence_partial'] is False
    assert context['capacity_posture']['label'] == 'Healthy'
    assert context['capacity_posture']['tone'] == 'normal'


def test_capacity_bottleneck_excludes_node_filesystem_reference() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {
                'cpu': {'capacity': 8, 'used': 2, 'available': 6, 'headroom': 75},
                'storage': {
                    'capacity': 100,
                    'used': 99,
                    'available': 1,
                    'headroom': 1,
                    'scheduling_resource': False,
                },
            }
        }
    )

    assert context['capacity_summary']['storage']['headroom'] == 1.0
    assert context['lowest_headroom_resource'] == 'cpu'
    assert context['lowest_headroom'] == 75.0


def test_capacity_risk_display_keeps_unavailable_headroom_as_na() -> None:
    presentation = _load_presentation_module()
    context = presentation.present_capacity_context(
        {
            'capacity_summary': {},
            'risk_summary': [
                {
                    'resource': 'storage',
                    'evidence_available': False,
                    'headroom': None,
                    'status': {'label': 'Unknown', 'tone': 'unknown'},
                }
            ],
        }
    )

    assert context['risk_summary'][0]['headroom_display'] == 'N/A'
    assert context['risk_summary'][0]['headroom_integer_display'] == 'N/A'
