from app.integrations.minio.client import _bucket_policy_exposure


def test_bucket_policy_exposure_detects_unrestricted_public_allow() -> None:
    assert _bucket_policy_exposure('{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject"}]}') == 'public'


def test_bucket_policy_exposure_keeps_conditional_wildcard_conservative() -> None:
    policy = '{"Statement":[{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Condition":{"IpAddress":{"aws:SourceIp":"10.0.0.0/8"}}}]}'
    assert _bucket_policy_exposure(policy) == 'restricted'


def test_bucket_policy_exposure_without_policy_is_private() -> None:
    assert _bucket_policy_exposure(None) == 'private'
