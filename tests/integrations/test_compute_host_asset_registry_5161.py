"""Issue #5161: pre-provision host assets cannot imply Ansible/cluster readiness."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.infrastructure_automation.host_registry_policy import (
    HostAssetRegistrationIntent,
    validate_host_asset_intent,
)
from app.models.compute_host import ComputeHostAsset


def _input() -> HostAssetRegistrationIntent:
    return HostAssetRegistrationIntent(
        asset_key='host-cp-01',
        name='Kubernetes Control Plane 01',
        site_key='lab-a',
        environment='laboratory',
        management_ipv4='10.25.1.11',
        ssh_port=22,
    )


def test_scope_only_validation_does_not_admit_ssh_or_execution():
    assert validate_host_asset_intent(_input()) is None
    assert ComputeHostAsset.__tablename__ == 'compute_host_assets'
    assert not hasattr(ComputeHostAsset, 'ssh_private_key')
    assert not hasattr(ComputeHostAsset, 'mutation_authorized')
    assert not hasattr(ComputeHostAsset, 'kubeconfig')


@pytest.mark.parametrize(
    ('changes', 'code'),
    [
        ({'asset_key': '../etc/passwd'}, 'HOST_IDENTITY_UNQUALIFIED'),
        ({'asset_key': ''}, 'HOST_IDENTITY_UNQUALIFIED'),
        ({'name': ''}, 'HOST_NAME_UNQUALIFIED'),
        ({'name': 'injected\nline'}, 'HOST_NAME_UNQUALIFIED'),
        ({'site_key': 'lab/a'}, 'HOST_SITE_UNQUALIFIED'),
        ({'environment': 'production'}, 'NON_PRODUCTION_ONLY'),
        ({'management_ipv4': '127.0.0.1'}, 'HOST_ENDPOINT_UNQUALIFIED'),
        ({'management_ipv4': '8.8.8.8'}, 'HOST_ENDPOINT_UNQUALIFIED'),
        ({'management_ipv4': '10.25.1.11 '}, 'HOST_ENDPOINT_UNQUALIFIED'),
        ({'ssh_port': 0}, 'HOST_ENDPOINT_UNQUALIFIED'),
        ({'ssh_port': True}, 'HOST_ENDPOINT_UNQUALIFIED'),
        ({'ssh_port': 70000}, 'HOST_ENDPOINT_UNQUALIFIED'),
    ],
)
def test_invalid_registration_intent_fails_closed(changes, code):
    assert validate_host_asset_intent(replace(_input(), **changes)) == code


def test_untrusted_mapping_cannot_skip_named_record_validation():
    assert validate_host_asset_intent({'asset_key': 'host-cp-01'}) == 'HOST_INPUT_UNQUALIFIED'
