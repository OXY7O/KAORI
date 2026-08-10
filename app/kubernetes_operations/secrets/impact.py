from __future__ import annotations

from app.common.inventory_generation import filter_current_generation
from app.inventory.resources.configuration_semantics import COLLECTED, POD_EVIDENCE_KEY, collection_state
from app.inventory.resources.pod_semantics import pod_operational_state
from app.kubernetes_operations.secrets.contracts import SecretImpactContext
from app.kubernetes_operations.secrets.live_service import LiveSecretSnapshot
from app.models import ClusterInventory, PodInventory


def get_secret_impact_context(target: LiveSecretSnapshot) -> SecretImpactContext:
    cluster_inventory = ClusterInventory.query.filter_by(cluster_id=target.cluster.id).first()
    evidence = dict(cluster_inventory.collection_evidence or {}) if cluster_inventory else {}
    pod_collection_state = collection_state(evidence, POD_EVIDENCE_KEY)
    if pod_collection_state != COLLECTED:
        return SecretImpactContext(
            items=[],
            collection_state=pod_collection_state,
            reported=False,
        )

    pods = filter_current_generation(PodInventory.query, PodInventory).filter_by(
        cluster_id=target.cluster.id,
        namespace=target.namespace,
    )
    impacts: dict[tuple[str, str], dict[str, object]] = {}
    for pod in pods.yield_per(250):
        references = pod.configuration_references or []
        if not any(
            str(reference.get('type') or '') == 'Secret' and str(reference.get('name') or '') == target.name
            for reference in references
        ):
            continue
        kind = str(pod.workload_type or 'Pod')
        name = str(pod.workload_name or pod.pod_name)
        state, tone, evidence_label = pod_operational_state(pod.phase, pod.ready)
        impacts[(kind, name)] = {
            'kind': kind,
            'name': name,
            'supporting_primary': f'{kind} workload',
            'supporting_secondary': evidence_label,
            'status': state,
            'status_tone': tone,
        }

    return SecretImpactContext(
        items=sorted(impacts.values(), key=lambda item: (str(item['kind']), str(item['name']))),
        collection_state=pod_collection_state,
        reported=True,
    )
