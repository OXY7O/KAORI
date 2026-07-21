from __future__ import annotations

from typing import Any

from app.models.prometheus import PrometheusInstance
from app.prometheus.service import PrometheusService


def validate_instance(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusService(instance).validate_integration()


def refresh_instance_health(instance: PrometheusInstance) -> dict[str, Any]:
    return PrometheusService(instance).refresh_runtime_health()
