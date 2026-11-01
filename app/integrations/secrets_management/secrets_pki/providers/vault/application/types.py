"""Web-independent Vault connection input for provider application use cases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VaultConnectionInput:
    name: str
    environment: str
    description: str | None
    endpoint: str
    namespace: str | None
    auth_mount: str
    role_id: str
    secret_id: str
    timeout: int
    enabled: bool
    kv2_mounts: tuple[str, ...] = ()
    pki_mounts: tuple[str, ...] = ()
    pki_stored_certs_enabled: bool = False
