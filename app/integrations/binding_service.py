from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions import db
from app.integrations.repository import get_cluster, get_provider_record


@dataclass(frozen=True, slots=True)
class CreatedSourceBinding:
    source: Any
    cluster: Any
    binding: Any


def create_cluster_source_binding(
    provider_type: str,
    *,
    source_id: int,
    cluster_id: str,
    role: str,
    priority: int,
    selector_label: str,
    selector_value: str,
    selector_operator: str,
) -> CreatedSourceBinding:
    provider = str(provider_type or '').strip().lower()
    if provider not in {'prometheus', 'alertmanager'}:
        raise ValueError(f'Unsupported source provider: {provider_type}')

    cluster = get_cluster(cluster_id)
    if cluster is None:
        raise ValueError('The selected Kubernetes scope no longer exists.')

    source = get_provider_record(provider, source_id)
    if source is None:
        raise ValueError(f'The selected {provider.title()} source no longer exists.')

    try:
        if provider == 'prometheus':
            from app.prometheus.service import create_prometheus_binding

            binding = create_prometheus_binding(
                instance=source,
                cluster=cluster,
                role=role,
                priority=priority,
                selector_label=selector_label,
                selector_value=selector_value,
                selector_operator=selector_operator,
            )
        else:
            from app.alertmanager.forms import AlertmanagerBindingForm
            from app.alertmanager.service import add_alertmanager_binding

            binding = add_alertmanager_binding(
                instance=source,
                form=AlertmanagerBindingForm(
                    scope_type='kubernetes_cluster',
                    scope_key=cluster.id,
                    binding_role=role,
                    priority=priority,
                    enabled=True,
                    selector_label=selector_label,
                    selector_value=selector_value,
                    selector_operator=selector_operator,
                ),
            )
    except Exception:
        db.session.rollback()
        raise

    return CreatedSourceBinding(source=source, cluster=cluster, binding=binding)
