from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT_TEMPLATES = ROOT / 'app/templates/reports'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


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
    assert 'text-base font-semibold leading-6 text-content-primary">Reporting Operational Posture</h2>' in overview_posture
    assert 'text-base font-semibold leading-6 text-content-primary">Report Coverage &amp; Artifact Estate</h2>' in overview_estate


def test_reports_hero_copy_is_compact_and_operational() -> None:
    overview = read('app/reports/overview/service.py')
    generate = read('app/reports/generate/service.py')
    generated = read('app/reports/generated/service.py')
    templates = read('app/reports/report_templates/service.py')
    schedules = read('app/reports/schedules/service.py')
    storage = read('app/reports/storage/service.py')

    assert 'Review reporting readiness, artifacts, automation, and report coverage across managed infrastructure.' in overview
    assert 'Build a governed report from connected data, scope, sections, and an approved output format.' in generate
    assert 'Review report records, artifact availability, generation state, and lifecycle actions.' in generated
    assert 'Manage protected system templates and reusable custom report structures.' in templates
    assert 'Automate report generation and delivery with timezone-aware schedules and retained run evidence.' in schedules
    assert 'Review artifact storage readiness, reference integrity, and lifecycle ownership.' in storage
