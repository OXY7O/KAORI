from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/kubernetes/dashboard/partials/_alerts_summary.html'


def test_alert_summary_distinguishes_no_alerts_from_source_failure() -> None:
    source = TEMPLATE.read_text()

    assert 'No Active Alerts' in source
    assert 'Alert Sources Temporarily Unavailable' in source
    assert 'Automatic Retry Enabled' in source
    assert 'Recovery Monitoring Active' in source
    assert 'No Active Alert Snapshot' not in source


def test_alert_summary_does_not_repeat_raw_snapshot_message_in_insight_footer() -> None:
    source = TEMPLATE.read_text()

    assert source.count('{{ dashboard.alerts_snapshot.message }}') == 1


def test_alert_snapshot_builder_sanitizes_legacy_snapshot_errors() -> None:
    source = (ROOT / 'app/kubernetes/dashboard/sections/alerts.py').read_text()

    assert 'else friendly_combined_alert_error()' in source
    assert "message=str(context.get('message') or unavailable_reason)" not in source
