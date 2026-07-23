from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[3]
REPORT_ROUTE_FILES = (
    ROOT / 'app/reports/generate/routes.py',
    ROOT / 'app/reports/export/routes.py',
    ROOT / 'app/reports/storage/routes.py',
)


def test_report_routes_do_not_use_flask_flash() -> None:
    for path in REPORT_ROUTE_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == 'flask'
            for alias in node.names
        }
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert 'flash' not in imported_names
        assert 'flash' not in calls


def test_transient_feedback_is_explicitly_non_persistent() -> None:
    path = ROOT / 'app/notifications/service.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'queue_transient_feedback'
    )
    source = ast.get_source_segment(path.read_text(encoding='utf-8'), function) or ''
    assert 'notification_saved=False' in source
    assert '_queue_quick_action_feedback(feedback)' in source
    assert 'persist_notification(' not in source


def test_report_mutations_record_operational_activity() -> None:
    for path in REPORT_ROUTE_FILES:
        source = path.read_text(encoding='utf-8')
        assert 'record_operational_activity(' in source

    assert "event_type='report_request_created'" in REPORT_ROUTE_FILES[0].read_text(encoding='utf-8')
    assert "event_type='report_pdf_generation'" in REPORT_ROUTE_FILES[1].read_text(encoding='utf-8')
    assert "event_type='report_storage_verification'" in REPORT_ROUTE_FILES[2].read_text(encoding='utf-8')
