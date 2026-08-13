from app.integrations.minio.client import _bucket_policy_exposure, _minio_admin_bucket_quota


def test_bucket_policy_exposure_detects_unrestricted_public_allow() -> None:
    assert (
        _bucket_policy_exposure('{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject"}]}')
        == 'public'
    )


def test_bucket_policy_exposure_keeps_conditional_wildcard_conservative() -> None:
    policy = '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Condition":{"IpAddress":{"aws:SourceIp":"10.0.0.0/8"}}}]}'
    assert _bucket_policy_exposure(policy) == 'restricted'


def test_bucket_policy_exposure_without_policy_is_private() -> None:
    assert _bucket_policy_exposure(None) == 'private'


class _QuotaResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


def test_minio_admin_bucket_quota_returns_configured_bytes(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(200, {'quota': 20 * 1024**3, 'quotatype': 'hard'}),
    )

    quota_bytes, quota_state = _minio_admin_bucket_quota(
        endpoint='https://minio.example.test',
        access_key='access-key',
        secret_key='secret-key',
        region='us-east-1',
        bucket_name='documents',
        timeout=5,
        verify_ssl=True,
    )

    assert quota_bytes == 20 * 1024**3
    assert quota_state == 'configured'


def test_minio_admin_bucket_quota_maps_zero_to_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(200, {'quota': 0}),
    )

    assert _minio_admin_bucket_quota(
        endpoint='https://minio.example.test',
        access_key='access-key',
        secret_key='secret-key',
        region='us-east-1',
        bucket_name='documents',
        timeout=5,
        verify_ssl=True,
    ) == (None, 'not_configured')


def test_minio_admin_bucket_quota_permission_gap_does_not_fail_inventory(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.integrations.minio.client.requests.get',
        lambda *args, **kwargs: _QuotaResponse(403),
    )

    assert _minio_admin_bucket_quota(
        endpoint='https://minio.example.test',
        access_key='access-key',
        secret_key='secret-key',
        region='us-east-1',
        bucket_name='documents',
        timeout=5,
        verify_ssl=True,
    ) == (None, 'not_collected')
