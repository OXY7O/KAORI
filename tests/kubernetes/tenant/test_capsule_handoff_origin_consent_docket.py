"""Capsule controller collector/consent proof contracts (#1229), AUTHORED NOT RUN."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
from uuid import UUID

import pytest

from app.kubernetes.tenant.capsule_handoff_collector_receipt import (
    inspect_capsule_collector_receipt,
)
from app.kubernetes.tenant import capsule_handoff_collector_key_resolution as key_resolution
from app.kubernetes.tenant import capsule_handoff_consent_identity as consent_identity
from app.kubernetes.tenant.capsule_handoff_origin_consent_docket import (
    review_capsule_origin_consent_docket,
)
from app.kubernetes.tenant.capsule_handoff_resource_admission import (
    assess_capsule_resource_handoff_scope,
)
from app.kubernetes.tenant.capsule_handoff_resource_consent import (
    inspect_capsule_resource_consent,
)
from app.kubernetes.tenant.capsule_handoff_related_inventory import _canonical, _digest
from app.kubernetes.tenant.release_handoff_approval import _plan_hash
from app.kubernetes.tenant.release_handoff_inventory import handoff_fingerprint

_KEY = b'nonproduction-fixture-only-collector-key-material-32bytes'


def _fixture():
    now = datetime.now(UTC).isoformat()
    rows = [
        {
            'kind': 'ResourceQuota', 'namespace': 'ns-demo',
            'name': 'managed-budget', 'uid': 'quota-uid',
            'resource_version': '21', 'origin': 'kaori_correlated',
            'policy_sha256': 'a' * 64, 'metadata_sha256': 'b' * 64,
        },
    ]
    lists = [
        {
            'namespace': 'ns-demo', 'kind': kind,
            'list_resource_version': 'rv-21', 'count': 1 if kind == 'ResourceQuota' else 0,
        }
        for kind in ('ResourceQuota', 'LimitRange', 'RoleBinding')
    ]
    related_sha = _digest({'resources': rows, 'lists': lists})
    grq = {
        'status': 'observed_not_handoff_authorized',
        'served_version': 'v1beta2', 'list_resource_version': 'grq-rv',
        'resources': [], 'count': 0, 'blockers': [],
    }
    grq['scope_sha256'] = _digest({
        'api_version': 'v1beta2', 'list_resource_version': 'grq-rv',
        'resources': [],
    })
    components = [
        {
            'kind': 'CapsuleTenant', 'name': 'capsule-demo', 'uid': 'cr-uid',
            'resource_version': '15', 'authority': 'capsule',
            'ownership': 'external_or_unattributed',
            'handoff': 'external_acceptance_required',
            'capsule_spec_sha256': 'c' * 64,
            'capsule_related_resources_sha256': related_sha,
            'capsule_related_resources_count': '1',
            'capsule_shared_quota_sha256': grq['scope_sha256'],
            'capsule_rbac_lineage_sha256': 'd' * 64,
        },
        {
            'kind': 'Namespace', 'name': 'ns-demo', 'namespace': 'ns-demo',
            'uid': 'ns-uid', 'resource_version': '17',
            'authority': 'capsule', 'ownership': 'kaori_marker_correlated',
            'handoff': 'external_acceptance_required',
        },
    ]
    plan = {
        'tenant_id': 'tenant-1', 'cluster_id': 'cluster-1',
        'generation': 7, 'provider': 'capsule',
        'handoff_components': components,
        'handoff_fingerprint': handoff_fingerprint(components),
        'provider_identity': [
            {'kind': 'CapsuleTenant', 'name': 'capsule-demo', 'uid': 'cr-uid', 'resource_version': '15'},
            {'kind': 'Namespace', 'name': 'ns-demo', 'uid': 'ns-uid', 'resource_version': '17'},
        ],
        'successor_owner': 'platform-admin',
        'change_reference': 'CHG-1011', 'requested_by': 10,
        'requested_at': now,
    }
    plan['plan_sha256'] = _plan_hash(plan)
    related = {
        'status': 'read_only_related_inventory',
        'resources': rows, 'resource_count': len(rows),
        'list_snapshots': lists, 'resource_sha256': related_sha,
        'blockers': [], 'global_quota': grq,
        'rbac_lineage': {
            'status': 'contract_correlated_controller_origin_unverified',
            'lineage_sha256': 'd' * 64, 'contract_correlated': True,
            'controller_origin_verified': False, 'blockers': [],
        },
    }
    approval = {
        'status': 'acknowledged_pending_provider_handoff',
        'plan_sha256': plan['plan_sha256'], 'requested_by': 10,
        'approved_by': 11, 'approved_at': now,
        'provider_handoff_verified': False, 'release_authorized': False,
    }
    acceptance = {
        'status': 'platform_admin_handoff_accepted',
        'plan_sha256': plan['plan_sha256'], 'tenant_id': plan['tenant_id'],
        'cluster_id': plan['cluster_id'], 'generation': plan['generation'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'reviewed_by': 11, 'accepted_by': 12,
        'accepted_at': now, 'consent_verified': True,
        'provider_mutation_performed': False, 'provider_handoff_verified': False,
        'release_authorized': False, 'secret_material_persisted': False,
    }
    base = assess_capsule_resource_handoff_scope(plan=plan, related=related)
    targets = []
    claims = []
    for ix, row in enumerate(base['resources']):
        if row['inventory_decision'] not in (
            'candidate_kaori_metadata_handoff_review',
            'explicit_kaori_metadata_handoff_review',
        ):
            continue
        targets.append({
            'kind': row['kind'], 'namespace': row['namespace'], 'name': row['name'],
            'uid': row['uid'], 'resource_version': row['resource_version'],
            'policy_sha256': row['policy_sha256'], 'metadata_sha256': row['metadata_sha256'],
            'decision': 'proposed_metadata_labels_only',
            'proposed_label_keys': ['app.kubernetes.io/managed-by'],
        })
        claims.append({
            'source': 'kubernetes_apiserver_audit',
            'audit_id': str(UUID(int=ix + 1)),
            'event_at': now, 'stage': 'ResponseComplete', 'verb': 'patch',
            'cluster_id': plan['cluster_id'], 'tenant_id': plan['tenant_id'],
            'kind': row['kind'], 'namespace': row['namespace'], 'name': row['name'],
            'uid': row['uid'], 'resource_version': row['resource_version'],
            'response_code': 200, 'controller_principal_sha256': 'e' * 64,
            'policy_sha256': row['policy_sha256'],
            'metadata_sha256': row['metadata_sha256'],
        })
    manifest = {
        'contract_version': 'capsule-resource-successor-consent/v1',
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'generation': plan['generation'], 'plan_sha256': plan['plan_sha256'],
        'handoff_fingerprint': plan['handoff_fingerprint'],
        'worklist_sha256': base['worklist_sha256'],
        'resource_review_sha256': base['resource_review_sha256'],
        'change_reference': plan['change_reference'],
        'reviewed_by': 11, 'accepted_by': 12,
        'accepted_at': datetime.now(UTC).isoformat(),
        'transfer_targets': targets,
    }
    receipt = {
        'contract_version': 'capsule-apiserver-collector-receipt/v1',
        'collector_id': 'trusted-cluster-audit', 'key_id': 'operator-root-001',
        'batch_id': '00000000-0000-4000-8000-000000000077',
        'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
        'plan_sha256': plan['plan_sha256'],
        'worklist_sha256': base['worklist_sha256'],
        'resource_review_sha256': base['resource_review_sha256'],
        'claims_sha256': _digest(claims),
        'captured_at': datetime.now(UTC).isoformat(),
        'auth_tag_sha256': '0' * 64,
    }
    _sign(receipt)
    return plan, related, approval, acceptance, base, claims, receipt, manifest


def _sign(receipt, key=_KEY):
    payload = {k: receipt[k] for k in sorted(receipt) if k != 'auth_tag_sha256'}
    receipt['auth_tag_sha256'] = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


def _collector(base, claims, receipt, key=_KEY):
    return inspect_capsule_collector_receipt(
        resource_report=base, claims=claims, receipt=receipt,
        trusted_collector_id='trusted-cluster-audit',
        trusted_key_id='operator-root-001', trusted_hmac_key=key,
    )


def _consent(plan, base, approval, acceptance, manifest):
    return inspect_capsule_resource_consent(
        plan=plan, resource_report=base, approval=approval,
        acceptance=acceptance, manifest=manifest,
    )


def test_exact_mac_receipt_and_all_resource_consent_remain_non_authorizing():
    plan, related, approval, acceptance, base, claims, receipt, manifest = _fixture()
    assert base['source_candidate_count'] == 2
    collector = _collector(base, claims, receipt)
    assert collector['collector_mac_verified'] is True
    assert collector['apiserver_audit_integrity_verified'] is False
    assert collector['audit_batch_replay_prevention_verified'] is False
    consent = _consent(plan, base, approval, acceptance, manifest)
    assert consent['resource_count'] == 2
    assert consent['independent_actor_separation_shape_valid'] is True
    assert consent['consent_source_authenticated'] is False
    assert consent['independent_consent_record_committed'] is False
    docket = review_capsule_origin_consent_docket(
        plan=plan, related=related, approval=approval, acceptance=acceptance,
        claims=claims, collector_receipt=receipt, consent_manifest=manifest,
        trusted_collector_id='trusted-cluster-audit',
        trusted_key_id='operator-root-001', trusted_hmac_key=_KEY,
    )
    assert docket['candidate_count'] == docket['audit_claim_count'] == docket['consent_target_count'] == 2
    assert docket['collector_mac_verified'] is True
    assert docket['controller_origin_attested'] is False
    assert docket['resource_specific_handoff_admitted'] is False
    assert docket['provider_execution_admitted'] is False
    assert docket['release_authorized'] is False
    assert 'trusted-cluster-audit' not in docket['review_docket_sha256']
    assert _KEY.hex() not in str(docket)


@pytest.mark.parametrize('mutation', [
    lambda r: r.update(plan_sha256='1' * 64),
    lambda r: r.update(cluster_id='wrong'),
    lambda r: r.update(worklist_sha256='a' * 64),
    lambda r: r.update(resource_review_sha256='a' * 64),
    lambda r: r.update(collector_id='untrusted-cluster-audit'),
    lambda r: r.update(key_id='unregistered-root'),
    lambda r: r.update(claims_sha256='b' * 64),
    lambda r: r.update(batch_id='not-a-uuid'),
    lambda r: r.update(secret='no-provider-secrets'),
])
def test_collector_receipt_rejects_forged_scope_or_unregistered_fields(mutation):
    *_, base, claims, receipt, manifest = _fixture()
    mutation(receipt)
    with pytest.raises((TypeError, ValueError)):
        _collector(base, claims, receipt)


def test_collector_valid_signature_from_wrong_key_is_not_trusted():
    *_, base, claims, receipt, manifest = _fixture()
    forged = deepcopy(receipt)
    _sign(forged, key=b'other-key-material-that-must-not-be-trusted-32bytes')
    with pytest.raises(ValueError, match='authentication failed'):
        _collector(base, claims, forged)


def test_collector_batch_expiry_is_rejected_even_when_resigned():
    *_, base, claims, receipt, manifest = _fixture()
    receipt['captured_at'] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    _sign(receipt)
    with pytest.raises(ValueError, match='stale'):
        _collector(base, claims, receipt)


def test_missing_key_and_claim_tampering_fails_before_origin_claim():
    *_, base, claims, receipt, manifest = _fixture()
    with pytest.raises(ValueError):
        _collector(base, claims, receipt, key=None)
    claims[0]['uid'] = 'replaced'
    with pytest.raises(ValueError):
        _collector(base, claims, receipt)


@pytest.mark.parametrize('mutation', [
    lambda m: m['transfer_targets'].pop(),
    lambda m: m['transfer_targets'].append(deepcopy(m['transfer_targets'][0])),
    lambda m: m['transfer_targets'][0].update(uid='rotated'),
    lambda m: m['transfer_targets'][0].update(resource_version='stale'),
    lambda m: m['transfer_targets'][0].update(policy_sha256='e' * 64),
    lambda m: m['transfer_targets'][0].update(decision='patch_resource_spec'),
    lambda m: m['transfer_targets'][0].update(spec={'hard': {'cpu': '999'}}),
    lambda m: m['transfer_targets'][0].update(proposed_label_keys=['foreign.example/other']),
    lambda m: m['transfer_targets'][0].update(proposed_label_keys=[['nested']]),
    lambda m: m.update(resource_review_sha256='0' * 64),
    lambda m: m.update(reviewed_by=12),
    lambda m: m.update(accepted_by=11),
])
def test_partial_stale_foreign_or_nonindependent_resource_consent_rejected(mutation):
    plan, related, approval, acceptance, base, claims, receipt, manifest = _fixture()
    mutation(manifest)
    with pytest.raises((TypeError, ValueError, KeyError)):
        _consent(plan, base, approval, acceptance, manifest)


def test_provider_owned_capsule_cr_may_not_be_included_in_successor_transfer():
    plan, related, approval, acceptance, base, claims, receipt, manifest = _fixture()
    candidate = deepcopy(manifest['transfer_targets'][0])
    candidate.update(kind='CapsuleTenant', namespace='', name='capsule-demo',
                     uid='cr-uid', resource_version='15', policy_sha256='c' * 64)
    manifest['transfer_targets'][0] = candidate
    with pytest.raises(ValueError):
        _consent(plan, base, approval, acceptance, manifest)


def test_controller_claim_coverage_must_include_namespace_and_quota():
    plan, related, approval, acceptance, base, claims, receipt, manifest = _fixture()
    claims.pop()
    receipt['claims_sha256'] = _digest(claims)
    _sign(receipt)
    with pytest.raises(ValueError, match='coverage'):
        review_capsule_origin_consent_docket(
            plan=plan, related=related, approval=approval, acceptance=acceptance,
            claims=claims, collector_receipt=receipt, consent_manifest=manifest,
            trusted_collector_id='trusted-cluster-audit',
            trusted_key_id='operator-root-001', trusted_hmac_key=_KEY,
        )


def test_manifest_must_bind_the_current_review_not_just_a_forged_flag():
    plan, related, approval, acceptance, base, claims, receipt, manifest = _fixture()
    approval['approved_by'] = plan['requested_by']
    manifest['reviewed_by'] = plan['requested_by']
    with pytest.raises(ValueError):
        _consent(plan, base, approval, acceptance, manifest)


def _human_claims(plan, base, approval, acceptance, manifest):
    """Only synthetic caller-supplied shapes; never authentic human identities."""
    reviewed = inspect_capsule_resource_consent(
        plan=plan, resource_report=base, approval=approval,
        acceptance=acceptance, manifest=manifest,
    )
    manifest_at = datetime.fromisoformat(manifest['accepted_at'])
    claims = []
    for ix, (action, actor, signed_at) in enumerate((
        ('independent_review', approval['approved_by'], manifest_at - timedelta(seconds=2)),
        ('successor_acceptance', acceptance['accepted_by'], manifest_at - timedelta(seconds=1)),
    )):
        claims.append({
            'contract_version': 'capsule-resource-human-session-attestation/v1',
            'attestation_id': str(UUID(int=ix + 101)),
            'issuer_id': 'company-idp', 'key_id': 'idp-key-1',
            'action': action, 'actor_user_id': actor,
            'session_sha256': format(ix + 101, '064x'),
            'challenge_sha256': format(ix + 201, '064x'),
            'authentication_method': 'phishing_resistant_mfa',
            'authenticated_at': (signed_at - timedelta(seconds=1)).isoformat(),
            'issued_at': signed_at.isoformat(),
            'expires_at': (signed_at + timedelta(minutes=4)).isoformat(),
            'tenant_id': plan['tenant_id'], 'cluster_id': plan['cluster_id'],
            'generation': plan['generation'],
            'plan_sha256': plan['plan_sha256'],
            'worklist_sha256': reviewed['worklist_sha256'],
            'resource_review_sha256': reviewed['resource_review_sha256'],
            'consent_manifest_sha256': reviewed['resource_consent_manifest_sha256'],
            'resource_scope_sha256': reviewed['resource_scope_sha256'],
            'mac_sha256': 'f' * 64,
        })
    return claims


def _identity_review(case, attestations, **changes):
    plan, related, approval, acceptance, base, claims, receipt, manifest = case
    opts = dict(
        plan=plan, resource_report=base, approval=approval,
        acceptance=acceptance, manifest=manifest, attestations=attestations,
        expected_issuer_id='company-idp', expected_key_id='idp-key-1',
    )
    opts.update(changes)
    return consent_identity.inspect_capsule_consent_session_attestations(**opts)


def test_two_distinct_session_envelopes_correlate_without_authenticating_humans():
    case = _fixture()
    plan, related, approval, acceptance, base, claims, receipt, manifest = case
    human = _human_claims(plan, base, approval, acceptance, manifest)
    observed = _identity_review(case, human)
    assert observed['attestation_count'] == 2
    assert observed['distinct_claimed_sessions'] is True
    assert len(observed['session_attestation_digest_sha256']) == 64
    assert observed['idp_session_origin_authenticated'] is False
    assert observed['mfa_challenge_verified'] is False
    assert observed['one_time_challenge_consumed'] is False
    assert observed['consent_source_authenticated'] is False
    assert observed['provider_execution_admitted'] is False
    assert 'session_sha256' not in str(observed)
    docket = review_capsule_origin_consent_docket(
        plan=plan, related=related, approval=approval, acceptance=acceptance,
        claims=claims, collector_receipt=receipt, consent_manifest=manifest,
        trusted_collector_id='trusted-cluster-audit',
        trusted_key_id='operator-root-001', trusted_hmac_key=_KEY,
        identity_attestations=human,
        expected_identity_issuer_id='company-idp',
        expected_identity_key_id='idp-key-1',
    )
    assert docket['identity_attestation_count'] == 2
    assert docket['identity_attestations_sha256'] == observed['session_attestation_digest_sha256']
    assert docket['human_consent_authenticated'] is False
    assert docket['release_authorized'] is False


@pytest.mark.parametrize('mutate', [
    lambda c: c[0].update(actor_user_id=12),
    lambda c: c[1].update(actor_user_id=11),
    lambda c: c[0].update(action='successor_acceptance'),
    lambda c: c[1].update(session_sha256=c[0]['session_sha256']),
    lambda c: c[1].update(challenge_sha256=c[0]['challenge_sha256']),
    lambda c: c[1].update(attestation_id=c[0]['attestation_id']),
    lambda c: c[0].update(tenant_id='foreign'),
    lambda c: c[1].update(plan_sha256='0' * 64),
    lambda c: c[1].update(resource_review_sha256='0' * 64),
    lambda c: c[0].update(consent_manifest_sha256='0' * 64),
    lambda c: c[0].update(resource_scope_sha256='0' * 64),
    lambda c: c[1].update(authentication_method='password_only'),
    lambda c: c[0].update(issuer_id='caller-controlled'),
    lambda c: c[0].update(key_id='rotated'),
    lambda c: c[0].update(mac_sha256='not-sha'),
    lambda c: c[0].update(expires_at='2001-01-01T00:00:00+00:00'),
    lambda c: c[1].update(issued_at='2001-01-01T00:00:00+00:00'),
    lambda c: c[0].update(secret='NEVER'),
])
def test_forged_cross_scope_replayed_or_stale_human_claim_is_rejected(mutate):
    case = _fixture()
    plan, _, approval, acceptance, base, _, _, manifest = case
    human = _human_claims(plan, base, approval, acceptance, manifest)
    mutate(human)
    with pytest.raises((ValueError, TypeError, KeyError)):
        _identity_review(case, human)


def test_claimed_valid_signature_cannot_open_source_gated_idp_verifier(monkeypatch):
    case = _fixture()
    plan, related, approval, acceptance, base, claims, receipt, manifest = case
    human = _human_claims(plan, base, approval, acceptance, manifest)

    class ExplodingIssuer:
        def read_verification_key(self, **kwargs):
            raise AssertionError('Key broker must NOT be used under source HOLD.')

    class ExplodingPin:
        def expected_key_fingerprint(self, **kwargs):
            raise AssertionError('Key policy must NOT be used under source HOLD.')

    for first, second in ((False, False), (False, True), (True, False)):
        monkeypatch.setattr(consent_identity, '_IDENTITY_MAC_VERIFIER_ENABLED', first)
        monkeypatch.setattr(consent_identity, '_AUTHENTICATED_HUMAN_SESSION_INGRESS_ENABLED', second)
        with pytest.raises(PermissionError, match='source-disabled'):
            consent_identity.review_capsule_consent_idp_mac_staged(
                plan=plan, resource_report=base, approval=approval,
                acceptance=acceptance, manifest=manifest, attestations=human,
                expected_issuer_id='company-idp', expected_key_id='idp-key-1',
                broker=ExplodingIssuer(), operator_policy=ExplodingPin(),
            )


def test_key_broker_resolution_is_source_disabled_before_secret_access(monkeypatch):
    case = _fixture()
    plan, related, approval, acceptance, base, claims, receipt, manifest = case

    class ExplodingBroker:
        def read_key(self, **kwargs):
            raise AssertionError('Vault/KMS key read forbidden under HOLD.')

        def read_pin(self, **kwargs):
            raise AssertionError('Vault/KMS pin read forbidden under HOLD.')

    class ExplodingPolicy:
        def expected_fingerprint(self, **kwargs):
            raise AssertionError('Operator registry read forbidden under HOLD.')

    for first, second in ((False, False), (False, True), (True, False)):
        monkeypatch.setattr(key_resolution, '_COLLECTOR_RESOLVER_ENABLED', first)
        monkeypatch.setattr(key_resolution, '_TRUSTED_COLLECTOR_INGRESS_ENABLED', second)
        with pytest.raises(PermissionError, match='source-disabled'):
            key_resolution.review_capsule_collector_via_broker_staged(
                resource_report=base, claims=claims, receipt=receipt,
                broker=ExplodingBroker(), operator_policy=ExplodingPolicy(),
                expected_cluster_id=plan['cluster_id'],
                expected_collector_id='trusted-cluster-audit',
                expected_key_id='operator-root-001',
            )


def test_docket_rejects_issuer_fields_without_actual_session_envelopes():
    case = _fixture()
    plan, related, approval, acceptance, base, claims, receipt, manifest = case
    with pytest.raises(ValueError):
        review_capsule_origin_consent_docket(
            plan=plan, related=related, approval=approval, acceptance=acceptance,
            claims=claims, collector_receipt=receipt, consent_manifest=manifest,
            trusted_collector_id='trusted-cluster-audit',
            trusted_key_id='operator-root-001', trusted_hmac_key=_KEY,
            expected_identity_issuer_id='company-idp',
        )
