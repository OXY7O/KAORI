"""Fail-closed tests for exact #4799 committed inventory membership."""
import pytest

from app.infrastructure_automation.remote_facts_command import RemoteFactsCommandDenied
from app.infrastructure_automation.remote_facts_inventory_membership import (
    require_exact_inventory_membership,
)


def test_exact_unique_member_is_review_only_alias():
    assert require_exact_inventory_membership(
        asset_id="asset-01",
        inventory_host="node-01.example.internal",
        committed_asset_hosts={"asset-01": "node-01.example.internal"},
    ) == "node-01.example.internal"


@pytest.mark.parametrize(
    ("asset", "host", "members"),
    [
        ("asset-02", "node-01", {"asset-01": "node-01"}),
        ("asset-01", "node-02", {"asset-01": "node-01"}),
        ("asset-01", "node-01", {"asset-01": "node-01", "asset-02": "node-01"}),
        ("asset-01", "node-01", {"asset-01": "node-01", "asset-02": "NODE-01"}),
        ("asset-01", "all", {"asset-01": "all"}),
        ("asset-01", "192.0.2.10", {"asset-01": "192.0.2.10"}),
        ("asset-01", "node-01", {}),
        ("asset-01", "node-01", {"asset-01": 42}),
        ("asset-01", "node-01", {"asset-01": "node-01", 42: "node-02"}),
        ("", "node-01", {"": "node-01"}),
        (" asset-01", "node-01", {" asset-01": "node-01"}),
        ("asset-01", "node-01", None),
    ],
)
def test_denies_untrusted_or_ambiguous_membership(asset, host, members):
    with pytest.raises(RemoteFactsCommandDenied):
        require_exact_inventory_membership(
            asset_id=asset, inventory_host=host, committed_asset_hosts=members,
        )


def test_no_claimed_signature_or_authority_override():
    with pytest.raises(TypeError):
        require_exact_inventory_membership(
            asset_id="asset-01",
            inventory_host="node-01",
            committed_asset_hosts={"asset-01": "node-01"},
            approved=True,
        )
