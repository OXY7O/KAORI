from types import SimpleNamespace

from app.intelligence import service


class QueryStub:
    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        return self

    def all(self):
        return []


def test_inventory_recommendations_use_committed_generation(monkeypatch) -> None:
    models: list[str] = []
    query = QueryStub()

    monkeypatch.setattr(service.db, 'session', SimpleNamespace(query=lambda *args: query))

    def capture_generation(candidate, model):
        models.append(model.__name__)
        return candidate

    monkeypatch.setattr(service, 'filter_current_generation', capture_generation)

    rules = {
        'kubernetes.workload.latest_image_tag': {'rule_key': 'kubernetes.workload.latest_image_tag'},
        'kubernetes.pod.unhealthy_phase': {'rule_key': 'kubernetes.pod.unhealthy_phase'},
        'kubernetes.pod.high_restart_count': {'rule_key': 'kubernetes.pod.high_restart_count'},
        'kubernetes.node.not_ready': {'rule_key': 'kubernetes.node.not_ready'},
        'kubernetes.storage.binding_state': {'rule_key': 'kubernetes.storage.binding_state'},
    }

    service._build_latest_image_findings(rules)
    service._build_pod_health_findings(rules)
    service._build_node_readiness_findings(rules)
    service._build_storage_binding_findings(rules)

    assert models.count('PodInventory') == 3
    assert models.count('NodeInventory') == 1
    assert models.count('StorageInventory') == 1
