from __future__ import annotations

import importlib.util
import subprocess
import sys
import types
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_filesystem_contract_accepts_user_reported_series_and_matches_pairs() -> None:
    script = r'''
import importlib.util, sys, types
from dataclasses import dataclass
from pathlib import Path
app=types.ModuleType("app"); app.__path__=[]; sys.modules["app"]=app
prom=types.ModuleType("app.prometheus"); prom.__path__=[]; sys.modules["app.prometheus"]=prom
exc=types.ModuleType("app.prometheus.exceptions")
class PrometheusError(Exception): pass
exc.PrometheusError=PrometheusError; sys.modules["app.prometheus.exceptions"]=exc
qp=types.ModuleType("app.prometheus.query_profiles"); qp.__path__=[]
@dataclass
class Query: expression: str
expressions={
"analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY": 'node_filesystem_size_bytes{mountpoint="/var", fstype!~"tmpfs|overlay"}',
"analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY": 'node_filesystem_avail_bytes{mountpoint="/var", fstype!~"tmpfs|overlay"}',
"analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY": 'node_filesystem_size_bytes{mountpoint="/", fstype!~"tmpfs|overlay"}',
"analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY": 'node_filesystem_avail_bytes{mountpoint="/", fstype!~"tmpfs|overlay"}',
}
qp.get_query=lambda key: Query(expressions.get(key, "vector(1)")); sys.modules["app.prometheus.query_profiles"]=qp
name="filesystem_effective_probe"
spec=importlib.util.spec_from_file_location(name, Path("app/prometheus/query_profiles/feature_contracts.py"))
module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
contract=next(item for item in module.FEATURE_CONTRACTS if item.key == "storage.filesystem")
class Client:
    def __init__(self): self.queries=[]
    def query(self, query):
        self.queries.append(query)
        mountpoint = "/var" if 'mountpoint="/var"' in query else "/"
        rows=[{"metric":{"cluster":"k8s-vm-dev","node":"k8s-master-development-001.pgn.co.id","mountpoint":mountpoint},"value":[0,"1"]}]
        return {"status":"success","data":{"result":rows}}
client=Client()
result=module._evaluate(client, contract, sample_namespace="default")
assert result["status"] == "ready", result
assert "matching /var pairs 1" in result["observed"], result["observed"]
assert "matching / pairs 1" in result["observed"], result["observed"]
assert all(query.startswith("count by (node, nodename, kubernetes_node, mountpoint)") for query in client.queries), client.queries
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_filesystem_contract_rejects_non_matching_size_and_available_identity() -> None:
    script = r'''
import importlib.util, sys, types
from dataclasses import dataclass
from pathlib import Path
app=types.ModuleType("app"); app.__path__=[]; sys.modules["app"]=app
prom=types.ModuleType("app.prometheus"); prom.__path__=[]; sys.modules["app.prometheus"]=prom
exc=types.ModuleType("app.prometheus.exceptions")
class PrometheusError(Exception): pass
exc.PrometheusError=PrometheusError; sys.modules["app.prometheus.exceptions"]=exc
qp=types.ModuleType("app.prometheus.query_profiles"); qp.__path__=[]
@dataclass
class Query: expression: str
expressions={
"analytics.storage.queries.NODE_VAR_FILESYSTEM_SIZE_QUERY": 'node_filesystem_size_bytes{mountpoint="/var"}',
"analytics.storage.queries.NODE_VAR_FILESYSTEM_AVAILABLE_QUERY": 'node_filesystem_avail_bytes{mountpoint="/var"}',
"analytics.storage.queries.NODE_ROOT_FILESYSTEM_SIZE_QUERY": 'node_filesystem_size_bytes{mountpoint="/"}',
"analytics.storage.queries.NODE_ROOT_FILESYSTEM_AVAILABLE_QUERY": 'node_filesystem_avail_bytes{mountpoint="/"}',
}
qp.get_query=lambda key: Query(expressions.get(key, "vector(1)")); sys.modules["app.prometheus.query_profiles"]=qp
name="filesystem_pair_mismatch"
spec=importlib.util.spec_from_file_location(name, Path("app/prometheus/query_profiles/feature_contracts.py"))
module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
contract=next(item for item in module.FEATURE_CONTRACTS if item.key == "storage.filesystem")
class Client:
    def query(self, query):
        mountpoint = "/var" if 'mountpoint="/var"' in query else "/"
        node = "worker-size" if "size_bytes" in query else "worker-available"
        return {"status":"success","data":{"result":[{"metric":{"node":node,"mountpoint":mountpoint},"value":[0,"1"]}]}}
result=module._evaluate(Client(), contract, sample_namespace="default")
assert result["status"] == "failed", result
assert "matching /var pairs 0" in result["observed"], result["observed"]
assert "align size and available series" in result["recommendation"], result["recommendation"]
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_full_validation_uses_extended_request_timeout() -> None:
    client = (ROOT / 'app/prometheus/client.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/prometheus/service.py').read_text(encoding='utf-8')
    assert 'request_timeout_seconds: int | None = None' in client
    assert 'return connect_timeout, read_timeout' in client
    assert 'request_timeout_seconds=max(int(config.timeout or 5), 30)' in service
