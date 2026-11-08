from __future__ import annotations

from app.integrations.registry.providers.harbor.client import HarborClient
from app.integrations.registry.providers.harbor.contracts import HarborConnectionSpec, HarborRetryPolicy
from app.models.harbor import HarborInstance


def connection_spec(source: HarborInstance) -> HarborConnectionSpec:
    return HarborConnectionSpec(
        endpoint=source.endpoint,
        auth_type=source.auth_type,
        username=source.username,
        password=source.password,
        timeout=source.timeout,
        verify_ssl=source.verify_ssl,
    )


def build_client(
    source: HarborInstance,
    *,
    transport_retries: int = 0,
    retry_backoff_seconds: float = 0.25,
) -> HarborClient:
    spec = connection_spec(source)
    return HarborClient(
        endpoint=spec.endpoint,
        auth_type=spec.auth_type,
        username=spec.username,
        password=spec.password,
        timeout=spec.timeout,
        verify_ssl=spec.verify_ssl,
        retry_policy=HarborRetryPolicy(
            transport_retries=transport_retries,
            backoff_seconds=retry_backoff_seconds,
        ),
    )
