from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KubernetesConnectionSpec:
    kubeconfig: str
    verify_ssl: bool = True
    allow_weak_tls: bool = False
    server: str | None = None
