from types import SimpleNamespace

from app.integrations.delivery.notification_channels.service import _report_id_for_delivery


def delivery(event_type='report.generated', asset_type='report', asset_key='42',
             event_key='report.generated:42'):
    return SimpleNamespace(event_type=event_type, asset_type=asset_type,
                           asset_key=asset_key, event_key=event_key)


def test_report_identity_is_exact_and_source_owned() -> None:
    assert _report_id_for_delivery(delivery()) == 42
    assert _report_id_for_delivery(delivery(asset_key='42', event_key='report.generated:43')) is None
    assert _report_id_for_delivery(delivery(asset_key='123foo')) is None
    assert _report_id_for_delivery(delivery(event_type='other')) is None
    assert _report_id_for_delivery(delivery(asset_type='job')) is None
    assert _report_id_for_delivery(delivery(asset_key='9999999999999999999')) is None
    assert _report_id_for_delivery(delivery(asset_key='٠١')) is None
