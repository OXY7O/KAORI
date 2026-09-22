from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT_TEMPLATES = ROOT / 'app/templates/reports'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_python_string(source: str, expected: str) -> bool:
    return any(
        isinstance(node, ast.Constant) and isinstance(node.value, str) and expected in node.value
        for node in ast.walk(ast.parse(source))
    )


def test_reports_web_templates_use_canonical_semibold_hierarchy() -> None:
    offenders: list[str] = []
    for template in REPORT_TEMPLATES.rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        if 'font-bold' in source:
            offenders.append(str(template.relative_to(ROOT)))
    assert offenders == []


def test_reports_heading_scale_matches_reviewed_kaori_surfaces() -> None:
    for template in REPORT_TEMPLATES.rglob('*.html'):
        source = template.read_text(encoding='utf-8')
        relative = template.relative_to(ROOT)
        for match in re.finditer(r'<h([2-4])\b[^>]*class="([^"]+)"', source):
            classes = match.group(2)
            if 'text-base' in classes and 'font-semibold' in classes:
                assert 'leading-6' in classes, relative
            if 'text-sm' in classes and 'font-semibold' in classes:
                assert 'leading-5' in classes, relative


def test_reports_primary_workspaces_use_canonical_section_examples() -> None:
    generate = read('app/templates/reports/generate/index.html')
    generated = read('app/templates/reports/generated/index.html')
    schedules = read('app/templates/reports/schedules/index.html')
    templates = read('app/templates/reports/report_templates/index.html')
    overview_posture = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    overview_estate = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')

    assert 'text-base font-semibold leading-6 text-content-primary">Build Governed Report</h2>' in generate
    assert 'text-base font-semibold leading-6 text-content-primary">Generated Reporting Posture</h2>' in generated
    assert 'text-base font-semibold leading-6 text-content-primary">Schedule Registry</h3>' in schedules
    assert '<h2 class="{{ table_ui.block_title_classes() }}">Template Registry</h2>' in templates
    assert (
        'text-base font-semibold leading-6 text-content-primary">Reporting Operational Posture</h2>' in overview_posture
    )
    assert (
        'text-base font-semibold leading-6 text-content-primary">Report Coverage &amp; Artifact Estate</h2>'
        in overview_estate
    )


def test_reports_typography_roles_follow_shared_kaori_primitives() -> None:
    table = read('app/templates/components/table_primitives.html')
    analytics = read('app/templates/analytics/components/_analysis_surfaces.html')

    assert 'text-base font-semibold text-content-primary' in table
    assert 'mt-1 text-sm leading-6 text-content-secondary' in table
    assert 'text-base font-semibold leading-6 text-content-primary' in analytics
    assert 'mt-1 text-sm leading-6 text-content-secondary' in analytics


def test_reports_block_headers_keep_shared_description_scale() -> None:
    cases = {
        'app/templates/reports/overview/partials/_reporting_operational_posture.html': (
            'Reporting Operational Posture',
            'Review worker readiness, recurring automation, storage health, and generation quality before creating or retrieving artifacts.',
        ),
        'app/templates/reports/overview/partials/_reporting_estate_capability.html': (
            'Report Coverage &amp; Artifact Estate',
            'Separate published report contracts from candidate and planned domains, then review the retained artifact estate and reusable automation.',
        ),
        'app/templates/reports/generate/index.html': (
            'Build Governed Report',
            'Complete five guided steps. Nothing is saved or queued until the final Review &amp; Queue step.',
        ),
        'app/templates/reports/storage/index.html': (
            'Storage Operations',
            'Review backend readiness, artifact integrity, and lifecycle ownership from one governed workspace.',
        ),
    }
    for relative, (title, description) in cases.items():
        source = read(relative.split('#', 1)[0])
        assert title in source, relative
        assert description in source, relative
        assert f'text-sm leading-6 text-content-secondary">{description}' in source, relative


def test_generate_primary_wizard_steps_use_block_description_scale() -> None:
    generate = read('app/templates/reports/generate/index.html')
    for title in (
        'Report Contract',
        'Infrastructure Scope',
        'Artifact Contract',
        'Report Content',
        'Review &amp; Queue',
    ):
        assert title in generate
    for old_class in (
        'text-base font-semibold leading-6 text-content-primary">Report Contract</h3>',
        'text-base font-semibold leading-6 text-content-primary">Infrastructure Scope</h3>',
        'text-base font-semibold leading-6 text-content-primary">Artifact Contract</h3>',
        'text-base font-semibold leading-6 text-content-primary">Report Content</h3>',
        'text-base font-semibold leading-6 text-content-primary">Review &amp; Queue</h3>',
    ):
        assert old_class in generate
    assert generate.count('text-sm leading-6 text-content-secondary') >= 6


def test_reports_nested_sections_keep_compact_helper_hierarchy() -> None:
    posture = read('app/templates/reports/overview/partials/_reporting_operational_posture.html')
    schedules = read('app/templates/reports/schedules/index.html')

    assert 'text-sm font-semibold leading-5 text-content-primary">Runtime Health</h3>' in posture
    assert (
        'text-xs leading-5 text-content-muted">Live dependencies required to create and retain reporting artifacts.'
        in posture
    )
    assert 'text-sm font-semibold leading-5 text-content-primary">Schedule Identity</h3>' in schedules
    assert (
        'text-xs leading-5 text-content-muted">Name the recurring automation and describe the operational purpose'
        in schedules
    )


def test_reports_hero_copy_is_compact_and_operational() -> None:
    files = {
        'overview': read('app/reports/overview/service.py'),
        'generate': read('app/reports/generate/service.py'),
        'generated': read('app/templates/reports/generated/index.html'),
        'templates': read('app/reports/report_templates/service.py'),
        'schedules': read('app/reports/schedules/service.py'),
        'storage': read('app/reports/storage/service.py'),
    }
    expected = {
        'overview': 'Review reporting readiness, artifacts, automation, and coverage.',
        'generate': 'Build governed reports from approved Analytics or Inventory data.',
        'generated': 'Review report execution, artifacts, storage, and lifecycle state.',
        'templates': ('Manage report templates for Analytics and Inventory output formats.'),
        'schedules': 'Automate Analytics and Inventory reports with governed schedules.',
        'storage': 'Review report storage readiness, integrity, and artifact lifecycle.',
    }
    for key, value in expected.items():
        assert has_python_string(files[key], value), key
