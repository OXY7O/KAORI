"""Committed Vault PKI ↔ Kubernetes TLS overlap uses source-owned ORM evidence."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.kubernetes.governance.tls_certificates.constants import TLS_COLLECTION_COLLECTED
from app.models.cluster import Cluster
from app.models.governance import TLSCertificateCollectionState, TLSCertificateInventory
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.certificate_delivery_read_model import build_certificate_delivery_overlap

AT = datetime(2026, 10, 22, 11, 0, tzinfo=UTC)
FP = 'a' * 64


@pytest.fixture
def committed_sources():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-fixture-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        INTEGRATION_CREDENTIAL_KEY=Fernet.generate_key().decode('ascii'),
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            Cluster.__table__,
            IntegrationInstance.__table__,
            VaultInstance.__table__,
            PKIStoredCertificateCollectionState.__table__,
            PKIStoredCertificateObservation.__table__,
            TLSCertificateCollectionState.__table__,
            TLSCertificateInventory.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        provider = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='test-provider',
            environment='testing',
            enabled=True,
            readiness_status='ready',
            lifecycle_status='active',
        )
        cluster = Cluster(name='cluster-correlation-fixture', environment='testing')
        db.session.add_all([provider, cluster])
        db.session.flush()
        vault = VaultInstance(
            integration_instance_id=provider.id,
            endpoint='https://vault.invalid',
            auth_mount='approle',
            role_id='test-only',
            secret_id='not-a-credential',
            timeout=5,
            verify_ssl=True,
            pki_mounts=['pki'],
            pki_stored_certs_enabled=True,
        )
        db.session.add_all(
            [
                vault,
                PKIStoredCertificateCollectionState(
                    integration_instance_id=provider.id,
                    provider_namespace='',
                    mount='pki',
                    status='ready',
                    observed_stored_certificate_count=1,
                    last_observed_at=AT,
                    last_committed_at=AT,
                ),
                PKIStoredCertificateObservation(
                    integration_instance_id=provider.id,
                    provider_namespace='',
                    mount='pki',
                    serial_hex='65',
                    fingerprint_sha256=FP,
                    valid_from=AT - timedelta(days=4),
                    valid_until=AT + timedelta(days=90),
                    observation_status='observed',
                    last_observed_at=AT,
                ),
                TLSCertificateCollectionState(
                    cluster_id=cluster.id,
                    secret_collection_status=TLS_COLLECTION_COLLECTED,
                    ingress_mapping_status=TLS_COLLECTION_COLLECTED,
                    collected_at=AT,
                ),
                TLSCertificateInventory(
                    cluster_id=cluster.id,
                    namespace='private-namespace',
                    secret_name='private-tls-secret',
                    fingerprint_sha256=FP,
                    status='healthy',
                    secret_uid='12345678-1234-4234-8234-123456789abc',
                    controller_owner_refs=[
                        {
                            'kind': 'ExternalSecret',
                            'api_group': 'external-secrets.io',
                            'uid': '12345678-1234-4234-8234-123456789abd',
                        },
                    ],
                    not_before=AT - timedelta(days=4),
                    not_after=AT + timedelta(days=90),
                    used_by=[
                        {'namespace': 'private-namespace', 'name': 'private-ingress', 'hosts': ['internal.example']}
                    ],
                    coverage_state='fully_covered',
                    declared_host_count=1,
                    covered_host_count=1,
                    collected_at=AT,
                ),
            ]
        )
        db.session.commit()
        try:
            yield provider.id, cluster.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _read():
    return build_certificate_delivery_overlap(
        authorized_to_view_kubernetes_tls=True,
        now=AT + timedelta(minutes=2),
    )


def test_two_committed_public_certificate_sources_identify_candidate_overlap(committed_sources):
    result = _read()
    assert result['status'] == 'overlap_observed'
    assert result['source_certificates'] == 1
    assert result['overlapping_certificates'] == 1
    assert result['matching_kubernetes_tls_secrets'] == 1
    assert result['ingress_reference_status'] == 'observed'
    assert result['matching_tls_secrets_referenced_by_ingress'] == 1
    assert result['matching_tls_secrets_covering_declared_hosts'] == 1
    assert result['vault_to_controller_proven'] is False
    assert result['delivery_proven'] is False
    assert result['endpoint_serving_verified'] is False
    assert 'private-tls-secret' not in repr(result)
    assert 'private-namespace' not in repr(result)


def test_kubernetes_source_failure_cannot_claim_delivery_overlap(committed_sources):
    cluster_id = committed_sources[1]
    state = db.session.get(TLSCertificateCollectionState, cluster_id)
    state.secret_collection_status = 'failed'
    db.session.commit()
    result = _read()
    assert result['status'] == 'source_unknown'
    assert result['matching_kubernetes_tls_secrets'] is None
    assert result['delivery_proven'] is False


def test_old_or_noncommitted_vault_source_does_not_prove_a_mismatch(committed_sources):
    provider_id = committed_sources[0]
    state = PKIStoredCertificateCollectionState.query.filter_by(
        integration_instance_id=provider_id,
    ).one()
    state.last_committed_at = AT - timedelta(days=3)
    db.session.commit()
    result = _read()
    assert result['status'] == 'source_unknown'
    assert result['overlapping_certificates'] is None


def test_revoked_enumeration_opt_in_removes_active_correlation_scope(committed_sources):
    provider_id = committed_sources[0]
    instance = VaultInstance.query.filter_by(integration_instance_id=provider_id).one()
    instance.pki_stored_certs_enabled = False
    db.session.commit()
    result = _read()
    assert result['status'] == 'not_configured'
    assert result['overlapping_certificates'] is None


def test_same_serial_not_same_fingerprint_is_not_delivery_evidence(committed_sources):
    tls = TLSCertificateInventory.query.one()
    tls.fingerprint_sha256 = 'b' * 64
    db.session.commit()
    result = _read()
    assert result['status'] == 'no_overlap_observed'
    assert result['overlapping_certificates'] == 0
    assert result['endpoint_serving_verified'] is False


def test_ingress_mapping_failure_retains_overlap_but_no_reference_claim(committed_sources):
    cluster_id = committed_sources[1]
    state = db.session.get(TLSCertificateCollectionState, cluster_id)
    state.ingress_mapping_status = 'collection_failed'
    db.session.commit()
    result = _read()
    assert result['status'] == 'overlap_observed'
    assert result['ingress_reference_status'] == 'unknown'
    assert result['matching_tls_secrets_referenced_by_ingress'] is None
    assert result['matching_tls_secrets_covering_declared_hosts'] is None
    assert result['endpoint_serving_verified'] is False


def test_declared_ingress_reference_with_partial_san_coverage_is_not_full(committed_sources):
    record = TLSCertificateInventory.query.one()
    record.coverage_state = 'partial'
    record.declared_host_count = 3
    record.covered_host_count = 1
    db.session.commit()
    result = _read()
    assert result['ingress_reference_status'] == 'observed'
    assert result['matching_tls_secrets_referenced_by_ingress'] == 1
    assert result['matching_tls_secrets_covering_declared_hosts'] == 0
    assert result['delivery_proven'] is False


def test_source_confirmed_without_ingress_reference_is_valid_observed_zero(committed_sources):
    record = TLSCertificateInventory.query.one()
    record.used_by = []
    record.coverage_state = 'no_declared_hosts'
    record.declared_host_count = 0
    record.covered_host_count = 0
    db.session.commit()
    result = _read()
    assert result['ingress_reference_status'] == 'not_observed'
    assert result['matching_tls_secrets_referenced_by_ingress'] == 0
    assert result['matching_tls_secrets_covering_declared_hosts'] == 0


def test_malformed_persisted_ingress_reference_blocks_correlation_safely(committed_sources):
    record = TLSCertificateInventory.query.one()
    record.used_by = [{'name': 'present-without-namespace'}]
    db.session.commit()
    result = _read()
    assert result['status'] == 'blocked'
    assert result['matching_tls_secrets_referenced_by_ingress'] is None
    assert 'present-without-namespace' not in repr(result)


def test_unavailable_ingress_results_cannot_disclose_private_names(committed_sources):
    result = _read()
    assert 'private-ingress' not in repr(result)
    assert 'private-namespace' not in repr(result)
    assert 'internal.example' not in repr(result)


def test_uid_qualified_public_certificate_overlap_is_distinct_from_delivery(committed_sources):
    result = _read()
    assert result['matching_tls_secrets_with_object_uid'] == 1
    assert result['object_identity_status'] == 'qualified'
    assert result['vault_to_controller_proven'] is False
    assert result['delivery_proven'] is False
    assert result['endpoint_serving_verified'] is False


def test_legacy_tls_inventory_without_uid_does_not_fabricate_provenance(committed_sources):
    tls = TLSCertificateInventory.query.one()
    tls.secret_uid = None
    db.session.commit()
    result = _read()
    assert result['status'] == 'overlap_observed'
    assert result['matching_tls_secrets_with_object_uid'] is None
    assert result['object_identity_status'] == 'not_observed'
    assert result['delivery_proven'] is False


def test_malformed_committed_object_uid_is_not_qualified(committed_sources):
    tls = TLSCertificateInventory.query.one()
    tls.secret_uid = 'private-namespace/private-tls-secret'
    db.session.commit()
    result = _read()
    assert result['matching_tls_secrets_with_object_uid'] is None
    assert result['object_identity_status'] == 'not_observed'
    assert 'private-namespace' not in repr(result)


def test_kubernetes_secret_recreation_changes_uid_without_identity_carryover(committed_sources):
    first = _read()
    tls = TLSCertificateInventory.query.one()
    previous_uid = tls.secret_uid
    tls.secret_uid = '12345678-1234-4234-8234-123456789abd'
    db.session.commit()
    changed = _read()
    assert previous_uid != tls.secret_uid
    assert first['matching_tls_secrets_with_object_uid'] == 1
    assert changed['matching_tls_secrets_with_object_uid'] == 1
    assert first['delivery_proven'] is False and changed['delivery_proven'] is False
    # The prior object's UID cannot be reused as controller materialization proof.


def test_supported_owner_evidence_is_candidate_only(committed_sources):
    result = _read()
    assert result['controller_owner_reference_status'] == 'candidate_observed'
    assert result['matching_tls_secrets_with_controller_owner'] == 1
    assert result['delivery_proven'] is False
    assert result['vault_to_controller_proven'] is False
    assert result['endpoint_serving_verified'] is False
    assert 'external-secrets.io' not in repr(result)


def test_unmanaged_tls_secret_has_observed_zero_owner_candidates(committed_sources):
    record = TLSCertificateInventory.query.one()
    record.controller_owner_refs = []
    db.session.commit()
    result = _read()
    assert result['controller_owner_reference_status'] == 'not_observed'
    assert result['matching_tls_secrets_with_controller_owner'] == 0
    assert result['status'] == 'overlap_observed'


def test_legacy_or_corrupt_owner_reference_is_partial_not_fabricated_zero(committed_sources):
    record = TLSCertificateInventory.query.one()
    record.controller_owner_refs = None
    db.session.commit()
    result = _read()
    assert result['controller_owner_reference_status'] == 'partial'
    assert result['matching_tls_secrets_with_controller_owner'] is None
    record.controller_owner_refs = [{'kind': 'ExternalSecret', 'uid': 'noncanonical'}]
    db.session.commit()
    result = _read()
    assert result['controller_owner_reference_status'] == 'partial'
    assert result['matching_tls_secrets_with_controller_owner'] is None
    assert 'noncanonical' not in repr(result)


def test_owner_reference_with_old_secret_uid_is_not_materialization_proof(committed_sources):
    old = _read()
    record = TLSCertificateInventory.query.one()
    record.secret_uid = '12345678-1234-4234-8234-123456789abe'
    db.session.commit()
    new = _read()
    assert old['controller_owner_reference_status'] == 'candidate_observed'
    assert new['controller_owner_reference_status'] == 'candidate_observed'
    assert new['delivery_proven'] is False
    # Receiver identity changed; a future source receipt must reference this
    # new exact Secret UID, never the previous object at the same name.
