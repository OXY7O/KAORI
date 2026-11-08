from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_schedule_post_does_not_rewrite_invalid_sections_and_period() -> None:
    service = (ROOT / 'app/reports/schedules/service.py').read_text(encoding='utf-8')
    generate = (ROOT / 'app/reports/generate/service.py').read_text(encoding='utf-8')
    assert 'get_form_state_from_form(form, for_submission=True)' in service
    assert 'for_submission: bool = False' in generate
    assert 'submitted_sections if for_submission else' in generate
    assert "if not form_state['name']:" in service


def test_registered_schedule_delivery_domains_come_from_catalog() -> None:
    support = (ROOT / 'app/reports/schedules/support.py').read_text(encoding='utf-8')
    script = (ROOT / 'app/static/js/report_schedules.js').read_text(encoding='utf-8')
    assert (
        "supported_domains = sorted({str(item.get('domain') or 'kubernetes') for item in REPORT_TYPE_OPTIONS})"
        in support
    )
    assert 'for domain in supported_domains:' in support
    assert "('kubernetes', 'object_storage')" not in support
    assert 'domains.includes(reportDomain)' in script
