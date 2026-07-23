from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]


def _filter_expressions(relative_path: str) -> str:
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return ast.dump(tree, include_attributes=False)


def test_primary_conflict_queries_include_canonical_enabled_state() -> None:
    for relative_path in (
        'app/integrations/prometheus/binding_management.py',
        'app/integrations/alertmanager/binding_management.py',
    ):
        tree = _filter_expressions(relative_path)
        assert "attr='enabled'" in tree
        assert "attr='is_'" in tree
