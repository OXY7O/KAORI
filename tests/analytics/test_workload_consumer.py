from types import SimpleNamespace

from app.analytics.workload.service import WorkloadAnalysisService


class FakeConsumer:
    def __init__(self):
        self.calls = []

    def requirements(self, capabilities):
        self.calls.append(("requirements", capabilities))
        return SimpleNamespace(ok=True, payload={"missing_capabilities": []})

    def query(self, query, required_capabilities):
        self.calls.append(("query", query, required_capabilities))
        return {"data": {"result": [{"metric": {"namespace": "default"}, "value": [0, "1"]}]}}

    def status(self):
        return SimpleNamespace(ok=True, payload={"response_time_ms": 12}, diagnostics=())


def build_service():
    consumer = FakeConsumer()
    prometheus = SimpleNamespace(consumer=consumer)
    utilization = SimpleNamespace(prometheus=prometheus)
    return WorkloadAnalysisService(utilization), consumer


def test_workload_requirements_use_complete_contract():
    service, consumer = build_service()
    result = service.requirements()
    assert result.ok
    assert consumer.calls[0][1] == service.REQUIRED_CAPABILITIES
    assert "workload_metrics" in service.REQUIRED_CAPABILITIES


def test_workload_queries_use_consumer_contract():
    service, consumer = build_service()
    rows = service.get_prometheus_result("vector(1)")
    assert rows[0]["metric"]["namespace"] == "default"
    assert consumer.calls[-1][2] == service.REQUIRED_CAPABILITIES
