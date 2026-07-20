from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_storage_contract_accepts_complete_var_pair_and_explains_partial_pair() -> None:
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
name="feature_contracts_regression"
spec=importlib.util.spec_from_file_location(name, Path("app/prometheus/query_profiles/feature_contracts.py"))
module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module)
contract=next(item for item in module.FEATURE_CONTRACTS if item.key == "storage.filesystem")
class Client:
    def __init__(self, include_available): self.include_available=include_available
    def query(self, query):
        observed = "/var" in query and ("size_bytes" in query or (self.include_available and "avail_bytes" in query))
        rows = [{"metric":{"cluster":"k8s-vm-dev","node":"worker-003","mountpoint":"/var","fstype":"xfs"},"value":[0,"75090624512"]}] if observed else []
        return {"status":"success","data":{"result":rows}}
ready=module._evaluate(Client(True), contract, sample_namespace="default")
partial=module._evaluate(Client(False), contract, sample_namespace="default")
assert ready["status"] == "ready", ready
assert partial["status"] == "failed", partial
assert "/var available No Data" in partial["observed"], partial["observed"]
assert "complete the preferred /var pair" in partial["recommendation"], partial["recommendation"]
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
