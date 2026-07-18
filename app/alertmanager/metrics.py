"""Deprecated compatibility exports for the pre-refactor normalizer module."""

from app.alertmanager.normalizers.alerts import normalize_alert as _normalize_alert
from app.alertmanager.normalizers.alerts import normalize_alerts as _normalize_alerts


def normalize_alertmanager_alerts(alerts):
    return _normalize_alerts(
        alerts,
        source_instance_id=None,
        source_instance_name='Legacy Alertmanager',
    )


def normalize_alertmanager_alert(alert):
    return _normalize_alert(
        alert,
        source_instance_id=None,
        source_instance_name='Legacy Alertmanager',
    ).to_dict()
