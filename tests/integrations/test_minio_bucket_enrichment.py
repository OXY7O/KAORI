from app.integrations.minio.client import (
    _bucket_policy_exposure,
    _minio_admin_bucket_quota,
    _minio_admin_data_usage,
)


def test_bucket_policy_exposure_detects_unrestricted_public_allow() -> None:
    policy = '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject"}]}'
    assert _bucket_policy_exposure(policy) == 'public'


def test_bucket_policy_exposure_keeps_conditional_wildcard_conservative() -> None:
    policy = (
        '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject",'
        '"Condition":{"IpAddress":{"aws:SourceIp":"10.0.0.0/8"}}}]}'
    )
    assert _bucket_policy_exposure(policy) == 'restricted'


def test_bucket_policy_exposure_without_policy_is_private() -> None:
    assert _bucket_policy_exposure(None) == 'private'


class _QuotaResponse:
    def __init__(self, status_code: int, payload: dict | None = None, *, text: str = ''):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.ok = 200 <= status_code < 300
        self.text = text

    def json(self):
        return self._payload


def _quota(**overrides):
    params = {
        'endpoint': 'https://minio.example.test',
        'access_key': 'access-key',
        'secret_key': 'secret-key',
        'region': 'us-east-1',
        'bucket_name': 'documents',
        'timeout': 5,
        'verify_ssl': True,
    }
    params.update(overrides)
    return _minio_admin_bucket_quota(**params)


def test_minio_admin_bucket_quota_reads_madmin_size_field(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(200, {'size': 20 * 1024**3, 'quotatype': 'hard'}),
    )

    evidence = _quota()

    assert evidence.quota_bytes == 20 * 1024**3
    assert evidence.state == 'configured'
    assert evidence.code == 'collected'
    assert evidence.source == 'minio_admin_api_v3'


def test_minio_admin_bucket_quota_keeps_legacy_quota_key_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(200, {'quota': 10 * 1024**3}),
    )

    assert _quota().quota_bytes == 10 * 1024**3


def test_minio_admin_bucket_quota_uses_legacy_value_when_size_is_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(
            200,
            {'quota': 25 * 1024**3, 'size': 0, 'quotatype': 'hard'},
        ),
    )

    evidence = _quota()

    assert evidence.quota_bytes == 25 * 1024**3
    assert evidence.state == 'configured'
    assert evidence.code == 'collected'


def test_minio_admin_bucket_quota_prefers_positive_size_over_legacy_value(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(
            200,
            {'quota': 10 * 1024**3, 'size': 40 * 1024**3, 'quotatype': 'hard'},
        ),
    )

    assert _quota().quota_bytes == 40 * 1024**3


def test_minio_admin_bucket_quota_maps_zero_to_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(200, {'size': 0}),
    )

    evidence = _quota()
    assert evidence.quota_bytes is None
    assert evidence.state == 'not_configured'
    assert evidence.code == 'not_configured'


def test_minio_admin_bucket_quota_records_access_denied_without_failing_inventory(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(403, {'Code': 'AccessDenied'}),
    )

    evidence = _quota()
    assert evidence.state == 'not_collected'
    assert evidence.code == 'access_denied'
    assert evidence.status_code == 403
    assert evidence.provider_code == 'AccessDenied'


def test_minio_admin_bucket_quota_records_signature_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(403, {'Code': 'SignatureDoesNotMatch'}),
    )

    evidence = _quota()
    assert evidence.code == 'signature_mismatch'
    assert evidence.provider_code == 'SignatureDoesNotMatch'


def test_minio_admin_bucket_quota_falls_forward_to_v4_when_v3_is_absent(monkeypatch) -> None:
    responses = iter(
        [
            _QuotaResponse(404, {'Code': 'NotFound'}),
            _QuotaResponse(200, {'size': 5 * 1024**3, 'quotatype': 'hard'}),
        ]
    )
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: next(responses),
    )

    evidence = _quota()
    assert evidence.quota_bytes == 5 * 1024**3
    assert evidence.source == 'minio_admin_api_v4'


def test_minio_admin_bucket_quota_marks_both_admin_generations_unsupported(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(404, {'Code': 'NotFound'}),
    )

    evidence = _quota()
    assert evidence.state == 'not_supported'
    assert evidence.code == 'not_supported'
    assert evidence.source == 'minio_admin_api_v4'


def _usage(**overrides):
    params = {
        'endpoint': 'https://minio.example.test',
        'access_key': 'access-key',
        'secret_key': 'secret-key',
        'region': 'us-east-1',
        'timeout': 5,
        'verify_ssl': True,
    }
    params.update(overrides)
    return _minio_admin_data_usage(**params)


def test_minio_admin_data_usage_collects_per_bucket_usage(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(
            200,
            {
                'lastUpdate': '2026-08-13T05:20:00Z',
                'bucketsUsageInfo': {
                    'documents': {'size': 12 * 1024**3, 'objectsCount': 1234},
                    'empty': {'size': 0, 'objectsCount': 0},
                },
            },
        ),
    )

    evidence = _usage()

    assert evidence.state == 'collected'
    assert evidence.code == 'collected'
    assert evidence.source == 'minio_admin_data_usage_v3'
    assert evidence.buckets['documents'] == (12 * 1024**3, 1234)
    assert evidence.buckets['empty'] == (0, 0)
    assert evidence.observed_at is not None


def test_minio_admin_data_usage_skips_invalid_usage_counters(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(
            200,
            {
                'bucketsUsageInfo': {
                    'valid-string': {'size': '1024', 'objectsCount': '2'},
                    'missing-size': {'size': None, 'objectsCount': 1},
                    'negative': {'size': -1, 'objectsCount': 1},
                    'fractional': {'size': 1.5, 'objectsCount': 1},
                    'boolean': {'size': True, 'objectsCount': 1},
                }
            },
        ),
    )

    evidence = _usage()

    assert evidence.buckets == {'valid-string': (1024, 2)}


def test_minio_admin_data_usage_records_access_denied_without_full_scan(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(403, {'Code': 'AccessDenied'}),
    )

    evidence = _usage()

    assert evidence.state == 'not_collected'
    assert evidence.code == 'access_denied'
    assert evidence.status_code == 403
    assert evidence.buckets == {}


def test_minio_admin_data_usage_falls_forward_to_v4_when_v3_is_absent(monkeypatch) -> None:
    responses = iter(
        [
            _QuotaResponse(404, {'Code': 'NotFound'}),
            _QuotaResponse(
                200,
                {
                    'lastUpdate': '2026-08-13T05:20:00Z',
                    'bucketsUsageInfo': {'documents': {'size': 1024, 'objectsCount': 1}},
                },
            ),
        ]
    )
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: next(responses),
    )

    evidence = _usage()

    assert evidence.source == 'minio_admin_data_usage_v4'
    assert evidence.buckets['documents'] == (1024, 1)
