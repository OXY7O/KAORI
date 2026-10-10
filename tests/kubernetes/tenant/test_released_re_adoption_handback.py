"""#1049: provider-preserving Released lineage and successor handback guard."""

from __future__ import annotations

import pytest

from app.kubernetes.tenant.discovery_adoption import (
    _require_re_adoption_handback_for_managed_release,
)


def test_observation_only_released_history_remains_eligible_for_canonical_discovery():
    _require_re_adoption_handback_for_managed_release(
        provider_evidence={'provider_mutation_performed': False},
        release_evidence={
            'status': 'released',
            'provider_mutation_performed': False,
            'provider_resource_deleted': False,
        },
    )


@pytest.mark.parametrize('provider,release', [
    ({'provider_mutation_performed': True}, {'status': 'released'}),
    ({}, {'status': 'released'}),
    ({'provider_mutation_performed': None}, {'status': 'released'}),
    ({'provider_mutation_performed': False},
     {'status': 'released', 'release_mode': 'managed_handoff'}),
    ({'provider_mutation_performed': False},
     {'status': 'released', 'provider_handoff_verified': True}),
])
def test_managed_or_unknown_prior_ownership_requires_fresh_successor_handback(provider, release):
    with pytest.raises(ValueError, match='verified successor handback'):
        _require_re_adoption_handback_for_managed_release(
            provider_evidence=provider, release_evidence=release,
        )
