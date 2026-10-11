from __future__ import annotations

import ast
from pathlib import Path

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
    return namespace['_aggregate_access_posture'](tones)


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
    tones: list[str], expected: tuple[str, str]
) -> None:
    assert aggregate_posture(tones) == expected


def test_access_overview_uses_only_permission_scoped_workspace_tones() -> None:
    presentation = (ROOT / 'app/access/overview/presentation.py').read_text(encoding='utf-8')
    assert "[workspace['status_tone'] for workspace in workspaces]" in presentation
    assert '_aggregate_access_posture(' in presentation
    assert "unknown_workspace_count = sum(" in presentation
