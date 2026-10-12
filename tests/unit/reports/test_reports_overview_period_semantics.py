from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.reports.overview.service import current_utc_month_bounds, get_artifact_statistics


def test_month_window_has_exclusive_end_across_year_boundary() -> None:
    start, end = current_utc_month_bounds(datetime(2026, 12, 31, 23, 59, tzinfo=UTC))
    assert start == datetime(2026, 12, 1, tzinfo=UTC)
    assert end == datetime(2027, 1, 1, tzinfo=UTC)


def test_month_window_uses_utc_not_browser_local_timezone() -> None:
    start, end = current_utc_month_bounds(datetime(2026, 11, 1, 0, 30, tzinfo=ZoneInfo('Asia/Jakarta')))
    assert start == datetime(2026, 10, 1, tzinfo=UTC)
    assert end == datetime(2026, 11, 1, tzinfo=UTC)
