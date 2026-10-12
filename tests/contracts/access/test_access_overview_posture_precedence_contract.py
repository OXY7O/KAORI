from __future__ import annotations

import ast
from pathlib import Path
from typing import Callable, cast

import pytest

ROOT = Path(__file__).resolve().parents[3]


def aggregate_posture(tones: list[str]) -> tuple[str, str]:
    """Execute the pure source function without importing the Flask/DB application."""

    source = ast.parse((ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8'))
    function = next(
        node
        for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == '_aggregate_access_posture'
    )
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<access-overview>', 'exec'), namespace)
    function_under_test = cast(Callable[[list[str]], tuple[str, str]], namespace['_aggregate_access_posture'])
    return function_under_test(tones)


@pytest.mark.parametrize(
    ('tones', 'expected'),
    [
        ([], ('Limited Evidence', 'unknown')),
        (['unknown'], ('Limited Evidence', 'unknown')),
        (['info'], ('Informational', 'info')),
        (['normal'], ('Current', 'normal')),
        (['normal', 'unknown'], ('Limited Evidence', 'unknown')),
        (['normal', 'unknown', 'info'], ('Informational', 'info')),
        (['normal', 'info', 'warning'], ('Review Required', 'warning')),
        (['critical', 'warning', 'info', 'unknown'], ('Critical Review', 'critical')),
    ],
)
def test_overview_aggregates_only_visible_workspace_tones(
    tones: list[str],
    expected: tuple[str, str],
) -> None:
    assert aggregate_posture(tones) == expected


def test_access_overview_uses_only_permission_scoped_workspace_tones() -> None:
    presentation = (ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8')
    assert "[workspace['status_tone'] for workspace in workspaces]" in presentation
    assert '_aggregate_access_posture(' in presentation
    assert "unknown_workspace_count = sum(" in presentation


@pytest.mark.parametrize(
    ('tones', 'expected'),
    [
        ([], (0, 0, 0, 0)),
        (['normal', 'unknown', 'info'], (3, 0, 0, 1)),
        (['warning'], (1, 1, 0, 0)),
        (['critical'], (1, 1, 1, 0)),
        (['warning', 'critical', 'warning', 'normal'], (4, 3, 1, 0)),
    ],
)
def test_access_overview_review_counts_are_defined_and_permission_scoped(
    tones: list[str],
    expected: tuple[int, int, int, int],
) -> None:
    source = ast.parse((ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8'))
    builder = next(
        node for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == 'build_access_overview'
    )
    names = {
        'workspace_count',
        'critical_workspace_count',
        'warning_workspace_count',
        'unknown_workspace_count',
        'attention_workspace_count',
    }
    statements = [
        node for node in builder.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
    ]
    assert len(statements) == len(names), 'Overview must define all metric counters'
    namespace: dict[str, object] = {
        'workspaces': [{'status_tone': tone} for tone in tones]
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=statements, type_ignores=[])),
                 '<access-review-counters>', 'exec'), namespace)
    assert (
        namespace['workspace_count'],
        namespace['attention_workspace_count'],
        namespace['critical_workspace_count'],
        namespace['unknown_workspace_count'],
    ) == expected
