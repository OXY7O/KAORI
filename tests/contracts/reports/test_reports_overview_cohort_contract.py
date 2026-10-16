from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_monthly_requests_have_two_bounded_utc_predicates() -> None:
    source = (ROOT / 'app/reports/overview/service.py').read_text()
    assert 'Report.created_at >= month_start' in source
    assert 'Report.created_at < next_month' in source
    assert 'All-time: ready or archived among resolved requests' in source
    assert 'Requests created this UTC calendar month' in source


def test_presented_completion_rate_is_not_implied_monthly() -> None:
    source = (ROOT / 'app/templates/reports/overview/partials/_reporting_operational_posture.html').read_text()
    assert 'all-time quality' in source
    assert 'Completion Rate measures resolved requests only across all history' in source
    assert 'current UTC calendar month' in source
