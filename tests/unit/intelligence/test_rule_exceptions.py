from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.intelligence.rule_exceptions import matching_rule_exception, rule_exception_status


def finding(bucket_id: str = '11') -> dict:
    return {
        'rule_key': f'object_storage.bucket.encryption_not_configured:7:{bucket_id}',
        'domain': 'object_storage',
        'evidence': {
            'asset_key': '7',
            'object_storage_system_id': '7',
            'bucket_id': bucket_id,
            'bucket_name': f'bucket-{bucket_id}',
        },
    }


def exception(*, scope_mode: str, keys: list[str] | None = None, expires_in_days: int = 30):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=1,
        public_id='risk-1',
        rule_key='object_storage.bucket.encryption_not_configured',
        asset_key='7',
        scope_mode=scope_mode,
        finding_keys_json=keys or [],
        starts_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(days=expires_in_days),
        revoked_at=None,
    )


def test_rule_asset_exception_covers_current_and_future_bucket_findings():
    row = exception(scope_mode='rule_asset')
    assert matching_rule_exception(finding('11'), rows=[row]) is row
    assert matching_rule_exception(finding('99'), rows=[row]) is row


def test_selected_finding_exception_only_covers_explicit_bucket_keys():
    covered = finding('11')['rule_key']
    row = exception(scope_mode='finding_keys', keys=[covered])
    assert matching_rule_exception(finding('11'), rows=[row]) is row
    assert matching_rule_exception(finding('12'), rows=[row]) is None


def test_expiring_exception_is_distinct_from_expired_exception():
    row = exception(scope_mode='rule_asset', expires_in_days=3)
    assert rule_exception_status(row)[0] == 'expiring'
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert rule_exception_status(row)[0] == 'expired'
