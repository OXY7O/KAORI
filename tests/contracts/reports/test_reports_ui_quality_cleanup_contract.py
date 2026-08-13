from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / 'app' / 'templates' / 'reports'
PDF_COMPONENT = REPORTS / 'pdf' / 'components' / 'analytics_publication.html'
SCHEDULES = REPORTS / 'schedules' / 'index.html'
SCHEDULE_JS = ROOT / 'app' / 'static' / 'js' / 'report_schedules.js'
STYLE_VERIFIER = ROOT / 'scripts' / 'verify_ui_style.py'
REUSE_VERIFIER = ROOT / 'scripts' / 'verify_ui_reuse.py'


def read(path: Path) -> str:
    return path.read_text()


def test_pdf_dynamic_width_is_owned_by_shared_publication_component() -> None:
    component = read(PDF_COMPONENT)
    assert 'macro percent_fill' in component
    assert 'style="width: {{ safe_value }}%' in component

    for template in sorted((REPORTS / 'pdf').glob('*.html')):
        source = read(template)
        assert 'style=' not in source, template
        assert re.search(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b', source) is None, template

    reuse = read(REUSE_VERIFIER)
    assert "'app/templates/reports/pdf/components/analytics_publication.html'" in reuse
    assert '_APPROVED_INLINE_STYLE_COMPONENTS' in reuse


def test_pdf_publication_titles_are_owned_by_publication_component_not_app_hero() -> None:
    style = read(STYLE_VERIFIER)
    assert '_APPROVED_CUSTOM_HERO_COMPONENTS' in style
    assert "'app/templates/reports/pdf/components/analytics_publication.html'" in style
    assert 'page_hero.title_classes()' not in read(PDF_COMPONENT)


def test_schedule_runtime_is_external_and_configuration_is_data_owned() -> None:
    schedules = read(SCHEDULES)
    runtime = read(SCHEDULE_JS)

    assert 'data-schedule-default-sections=' in schedules
    assert 'data-schedule-allowed-formats=' in schedules
    assert 'data-schedule-family-by-type=' in schedules
    assert 'data-schedule-open-dialog=' in schedules
    assert "filename='js/report_schedules.js'" in schedules
    assert re.search(r'<script\b(?![^>]*\bsrc\s*=)', schedules, re.IGNORECASE) is None

    assert 'dataset.scheduleDefaultSections' in runtime
    assert 'dataset.scheduleAllowedFormats' in runtime
    assert 'dataset.scheduleFamilyByType' in runtime
    assert 'dataset.scheduleOpenDialog' in runtime
    assert "document.body.addEventListener('htmx:afterSwap'" in runtime


def test_report_progress_uses_shared_progress_component() -> None:
    detail = read(REPORTS / 'generated' / 'detail.html')
    templates = read(REPORTS / 'report_templates' / 'index.html')

    assert 'components/progress_bar.html' in detail
    assert 'progress_bar.job_progress(' in detail
    assert 'progress_bar.determinate(' not in detail

    assert 'components/progress_bar.html' in templates
    assert 'progress_bar.bar(' in templates

    # Dynamic width remains owned by the approved shared progress component,
    # never by report-specific templates.
    assert 'style="width:' not in detail
    assert 'style="width:' not in templates
