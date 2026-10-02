from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLANNER = ROOT / 'scripts' / 'resolve_developer_check_plan.py'


def load_planner():
    spec = importlib.util.spec_from_file_location('kaori_developer_validation_plan_ui', PLANNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_ui_browser_changes_prepare_frontend_assets_before_tests() -> None:
    planner = load_planner()

    plan = planner.resolve_plan(('tests/ui/test_browser_smoke.py',), root=ROOT)

    assert plan.frontend is True
    assert plan.test_paths == ('tests/ui',)
