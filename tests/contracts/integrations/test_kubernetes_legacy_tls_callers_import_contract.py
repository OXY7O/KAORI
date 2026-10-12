"""Prevent application startup failure from retired Kubernetes weak TLS imports.

Kubernetes transport policy is exclusively applied by the canonical
client.build adapter to each Kubernetes SDK API client's pool.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY_TLS = "weak_tls_context"
TLS_MODULE = "app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.tls"


def test_no_kubernetes_application_source_imports_retired_tls_context() -> None:
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == TLS_MODULE:
                assert all(alias.name != LEGACY_TLS for alias in node.names), path


def test_sensitive_kubernetes_operations_and_inventory_import_without_retired_tls() -> None:
    for module_name in (
        "app.kubernetes.operations.secrets.live_service",
        "app.kubernetes.operations.secrets.create_service",
        "app.kubernetes.operations.secrets.replace_service",
        "app.kubernetes.operations.secrets.delete_service",
        "app.kubernetes.operations.secrets.reveal_service",
        "app.kubernetes.operations.configmaps.runtime",
        "app.kubernetes.inventory.synchronization",
        "app.kubernetes.governance.tls_certificates.collector",
    ):
        module = importlib.import_module(module_name)
        assert module is not None


def test_operational_calls_use_provider_scoped_tls_instead_of_process_global_override() -> None:
    adapter = (
        ROOT / "app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/adapter.py"
    ).read_text(encoding="utf-8")
    client = (
        ROOT / "app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/client.py"
    ).read_text(encoding="utf-8")
    for path in (
        "app/kubernetes/operations/secrets/live_service.py",
        "app/kubernetes/operations/configmaps/runtime.py",
    ):
        source = (ROOT / path).read_text(encoding="utf-8")
        assert "connection_for_cluster(cluster)" in source
        assert "'client.build'" in source
        assert LEGACY_TLS not in source
    assert "allow_weak_tls=bool(connection.allow_weak_tls)" in adapter
    assert "configure_weak_tls(" in client
    assert "enabled=self.allow_weak_tls" in client
