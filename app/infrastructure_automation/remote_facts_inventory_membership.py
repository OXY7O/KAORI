"""Fail-closed exact inventory membership review for #4799.

Pure candidate validation only. A committed inventory snapshot must be verified
against an independently trusted asset authority before any worker may use it.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.infrastructure_automation.remote_facts_command import (
    RemoteFactsCommandDenied,
    build_remote_facts_command,
)


def require_exact_inventory_membership(
    *,
    asset_id: str,
    inventory_host: str,
    committed_asset_hosts: Mapping[str, str],
) -> str:
    """Reject ambiguous aliases and cross-asset reuse, returning review-only host.

    The caller MUST independently attest the snapshot source, revision, signature,
    asset authority and target lock. A matching mapping is not SSH permission.
    """
    if type(asset_id) is not str or not asset_id or asset_id != asset_id.strip():
        raise RemoteFactsCommandDenied("Canonical asset ID is required")
    if type(inventory_host) is not str:
        raise RemoteFactsCommandDenied("Canonical inventory host is required")
    if not isinstance(committed_asset_hosts, Mapping) or not committed_asset_hosts:
        raise RemoteFactsCommandDenied("Committed inventory membership is required")
    # Never silently overwrite duplicate or ambiguous host ownership.
    if any(
        type(key) is not str or not key or type(value) is not str
        for key, value in committed_asset_hosts.items()
    ):
        raise RemoteFactsCommandDenied("Malformed inventory membership")
    if asset_id not in committed_asset_hosts:
        raise RemoteFactsCommandDenied("Asset is absent from committed inventory")
    if committed_asset_hosts[asset_id] != inventory_host:
        raise RemoteFactsCommandDenied("Inventory host differs from asset binding")
    build_remote_facts_command(inventory_host=inventory_host)
    owners = [
        key for key, value in committed_asset_hosts.items()
        if value.casefold() == inventory_host.casefold()
    ]
    if len(owners) != 1 or owners[0] != asset_id:
        raise RemoteFactsCommandDenied("Inventory alias has ambiguous asset ownership")
    return inventory_host
