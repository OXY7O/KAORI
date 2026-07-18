from __future__ import annotations

from app.alertmanager.client import AlertmanagerClient
from app.alertmanager.contracts import AlertmanagerConnectionSpec
from app.models.alertmanager import AlertmanagerInstance

AlertmanagerConnectionSource = AlertmanagerInstance


def connection_spec(source: AlertmanagerConnectionSource) -> AlertmanagerConnectionSpec:
    return AlertmanagerConnectionSpec(
        endpoint=source.endpoint,
        auth_type=source.auth_type,
        username=source.username,
        password=source.password,
        bearer_token=source.bearer_token,
        timeout=source.timeout,
        verify_ssl=source.verify_ssl,
    )


def build_client(source: AlertmanagerConnectionSource) -> AlertmanagerClient:
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
