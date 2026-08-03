from __future__ import annotations

import boto3

from app.storage.s3 import S3ArtifactStorage


def test_s3_client_receives_bounded_timeout_and_retry_policy(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        pass

    def fake_client(service_name: str, **kwargs):
        captured['service_name'] = service_name
        captured.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(boto3, 'client', fake_client)

    S3ArtifactStorage(
        bucket='kaori-reports',
        cache_dir=tmp_path,
        endpoint_url='http://minio:9000',
        force_path_style=True,
        connect_timeout_seconds=2,
        read_timeout_seconds=3,
        max_attempts=1,
    )

    assert captured['service_name'] == 's3'
    config = captured['config']
    assert config.connect_timeout == 2
    assert config.read_timeout == 3
    assert config.retries['total_max_attempts'] == 1
    assert config.s3['addressing_style'] == 'path'
