from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML_PDF = ROOT / 'app/reports/export/html_pdf'

_FAMILIES = (
    ('resource_utilization.py', 'build_resource_utilization_presentation', 'utilization'),
    ('alerts_anomalies.py', 'build_alerts_anomalies_presentation', 'alerts'),
    ('forecast_analysis.py', 'build_forecast_analysis_presentation', 'forecast'),
    ('analytics_overview.py', 'build_analytics_overview_presentation', 'overview'),
    ('top_consumers_analysis.py', 'build_top_consumers_analysis_presentation', 'top_consumers'),
    ('workload_analysis.py', 'build_workload_analysis_presentation', 'workload'),
)


def _function_span(source: str, name: str) -> int:
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    assert function.end_lineno is not None
    return function.end_lineno - function.lineno + 1


def _branch_points(source: str, name: str) -> int:
    tree = ast.parse(source)
    function = next(
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )
    points = 1
    for child in ast.walk(function):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.Match)):
            points += 1
        elif isinstance(child, ast.BoolOp):
            points += max(1, len(child.values) - 1)
        elif isinstance(child, ast.Try):
            points += len(child.handlers) + int(bool(child.orelse)) + int(bool(child.finalbody))
        elif isinstance(child, ast.comprehension):
            points += 1 + len(child.ifs)
    return points


def test_remaining_html_pdf_report_families_have_bounded_facades_and_owned_packages() -> None:
    for filename, builder_name, package_name in _FAMILIES:
        facade = HTML_PDF / filename
        source = facade.read_text(encoding='utf-8')

        assert len(source.splitlines()) <= 800, f'{filename} must remain below the 800-line module ceiling'
        assert _function_span(source, builder_name) <= 160, f'{builder_name} must remain below 160 lines'

        package = HTML_PDF / package_name
        assert package.is_dir(), f'{package_name}/ must own extracted {filename} presentation responsibilities'
        assert (package / '__init__.py').exists(), f'{package_name}/ must be an explicit Python package'
        ownership_modules = [path for path in package.glob('*.py') if path.name != '__init__.py']
        assert len(ownership_modules) >= 2, (
            f'{package_name}/ must use cohesive ownership modules, not one catch-all file'
        )


def test_shared_html_pdf_finding_normalization_stays_below_branch_ceiling() -> None:
    source = (HTML_PDF / 'normalization.py').read_text(encoding='utf-8')

    assert _branch_points(source, 'findings_from_value') <= 30
