from datetime import UTC, datetime
from pathlib import Path

from app.common.presentation import UserPresentationPreferences, present_user_datetime


def test_present_user_datetime_uses_explicit_preferences():
    value = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    preferences = UserPresentationPreferences(
        timezone_name='Asia/Jakarta',
        locale='en-US',
        date_format='year_month_day',
        time_format='24h',
    )

    rendered = present_user_datetime(value, preferences=preferences, include_timezone=True)

    assert rendered == '2026-07-18 19:00 WIB'


def test_runtime_overview_template_uses_presentation_ready_fields():
    template = Path('app/templates/integrations/partials/_runtime_overview.html').read_text()

    assert 'datetimeformat' not in template
    assert 'strftime(' not in template
    assert 'row.observed_at_display' in template
    assert 'row.latency_display' in template
    assert 'row.capability_attention_display' in template
