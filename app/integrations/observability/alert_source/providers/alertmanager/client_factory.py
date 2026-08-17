from __future__ import annotations

from app.integrations.observability.alert_source.providers.alertmanager.client import AlertmanagerClient
from app.integrations.observability.alert_source.providers.alertmanager.contracts import AlertmanagerConnectionSpec
from app.models.alertmanager import AlertmanagerInstance


def connection_spec(source: AlertmanagerInstance) -> AlertmanagerConnectionSpec:
    return AlertmanagerConnectionSpec(
        endpoint=source.endpoint,
        auth_type=source.auth_type,
        username=source.username,
        password=source.password,
        bearer_token=source.bearer_token,
        timeout=source.timeout,
        verify_ssl=source.verify_ssl,
    )


def build_client(source: AlertmanagerInstance) -> AlertmanagerClient:
    spec = connection_spec(source)
    return AlertmanagerClient(
        endpoint=spec.endpoint,
        auth_type=spec.auth_type,
        username=spec.username,
        password=spec.password,
        bearer_token=spec.bearer_token,
        timeout=spec.timeout,
        verify_ssl=spec.verify_ssl,
    )
