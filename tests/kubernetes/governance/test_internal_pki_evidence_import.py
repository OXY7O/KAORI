from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.governance.internal_certificates.evidence_import import (
    PKIEvidenceValidationError,
    import_attested_pki_metadata,
    validate_metadata_manifest,
)
from app.kubernetes.governance.internal_certificates.kubeadm_adapter import (
    prepare_kubeadm_metadata_manifest,
)
from app.kubernetes.governance.internal_certificates.service import (
    enrich_internal_pki_source_states,
    get_internal_certificate_inventory_page,
)
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.internal_certificates import InternalPKICertificateInventory, InternalPKIEvidenceBatch


def _manifest(cluster_id: str, *, collected_at: datetime | None = None) -> dict:
    now = collected_at or datetime.now(UTC)
    return {
        'schema_version': 'kaori.internal-pki-evidence.v1',
        'cluster_id': cluster_id,
        'node_name': 'control-plane-01',
        'source_kind': 'kubeadm_check_expiration',
        'source_version': 'v1.31.0',
        'collected_at': now.isoformat(),
        'coverage_state': 'complete',
        'reference': 'CHG-20261112-001',
        'certificates': [
            {
                'component': 'apiserver',
                'kind': 'leaf',
                'issuer': 'ca',
                'not_before': (now - timedelta(days=30)).isoformat(),
                'not_after': (now + timedelta(days=40)).isoformat(),
                'externally_managed': False,
            },
            {
                'component': 'ca',
                'kind': 'ca',
                'issuer': None,
                'not_before': None,
                'not_after': (now + timedelta(days=365)).isoformat(),
                'externally_managed': False,
            },
        ],
    }


@pytest.fixture()
def pki_repository_app():
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite+pysqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    with app.app_context():
        Cluster.__table__.create(db.engine)
        InternalPKIEvidenceBatch.__table__.create(db.engine)
        InternalPKICertificateInventory.__table__.create(db.engine)
        AuditEvent.__table__.create(db.engine)
        yield app
        db.session.remove()
        AuditEvent.__table__.drop(db.engine)
        InternalPKICertificateInventory.__table__.drop(db.engine)
        InternalPKIEvidenceBatch.__table__.drop(db.engine)
        Cluster.__table__.drop(db.engine)


def test_manifest_validates_metadata_without_accepting_pkcs_payload() -> None:
    payload = _manifest(str(uuid4()))
    normalized = validate_metadata_manifest(payload)
    assert len(normalized['certificates']) == 2
    assert [item['component'] for item in normalized['certificates']] == ['apiserver', 'ca']
    assert normalized['certificates'][0]['not_after'].tzinfo is not None


@pytest.mark.parametrize(
    ('change', 'expected'),
    (
        (lambda p: p.update({'private_key': '-----BEGIN PRIVATE KEY-----'}), 'missing or unexpected'),
        (lambda p: p['certificates'][0].update({'pem': '-----BEGIN CERTIFICATE-----'}), 'missing or unexpected'),
        (lambda p: p['certificates'][0].update({'kind': 'ca'}), 'kind'),
        (lambda p: p['certificates'][0].update({'component': 'kubelet-client'}), 'Unsupported'),
        (lambda p: p.update({'collected_at': '2026-11-12T15:00:00'}), 'UTC'),
        (lambda p: p['certificates'].append(dict(p['certificates'][0])), 'Duplicate'),
    ),
)
def test_manifest_fails_closed_for_untrusted_or_ambiguous_evidence(change, expected: str) -> None:
    payload = _manifest(str(uuid4()))
    change(payload)
    with pytest.raises(PKIEvidenceValidationError, match=expected):
        validate_metadata_manifest(payload)


def test_committed_pki_import_is_idempotent_and_supports_bounded_inventory(
    pki_repository_app,
) -> None:
    with pki_repository_app.app_context():
        cluster_id = str(uuid4())
        db.session.add(Cluster(id=cluster_id, name='PKI Pilot', environment='non-production'))
        db.session.commit()
        payload = _manifest(cluster_id)
        first, created = import_attested_pki_metadata(payload)
        assert created is True
        second, repeated = import_attested_pki_metadata(payload)
        assert repeated is False
        assert first.id == second.id
        assert InternalPKIEvidenceBatch.query.count() == 1
        assert InternalPKICertificateInventory.query.count() == 2
        assert AuditEvent.query.filter_by(action='internal_pki_operator_metadata_import').count() == 1

        page = get_internal_certificate_inventory_page({'cluster_id': cluster_id, 'cert_per_page': '5'})
        assert page['total'] == 2
        assert page['pagination']['per_page'] == 5
        assert {row['component'] for row in page['records']} == {'apiserver', 'ca'}
        assert all(row['source_kind'] == 'kubeadm_check_expiration' for row in page['records'])

        source_payload = {
            'records': [
                {
                    'id': cluster_id,
                    'collection_status': 'Not Collected',
                    'authority_status': 'Not Verified',
                    'expiry_status': 'Unknown',
                }
            ]
        }
        enrich_internal_pki_source_states(source_payload)
        assert source_payload['records'][0]['collection_status'] == 'Operator Attested'
        assert source_payload['records'][0]['authority_status'] == 'Operator Supplied'


def test_rejected_older_import_preserves_latest_committed_evidence(pki_repository_app) -> None:
    with pki_repository_app.app_context():
        cluster_id = str(uuid4())
        db.session.add(Cluster(id=cluster_id, name='PKI Pilot', environment='non-production'))
        db.session.commit()
        newer = _manifest(cluster_id)
        import_attested_pki_metadata(newer)
        old = _manifest(cluster_id, collected_at=datetime.now(UTC) - timedelta(days=3))
        with pytest.raises(PKIEvidenceValidationError, match='older'):
            import_attested_pki_metadata(old)
        assert InternalPKIEvidenceBatch.query.count() == 1
        assert InternalPKICertificateInventory.query.count() == 2



def _kubeadm_1364_report() -> dict:
    """Metadata-only synthetic fixture matching the operator-reviewed v1alpha3 shape."""
    families = {
        'admin.conf': 'ca',
        'apiserver': 'ca',
        'apiserver-etcd-client': 'etcd-ca',
        'apiserver-kubelet-client': 'ca',
        'controller-manager.conf': 'ca',
        'etcd-healthcheck-client': 'etcd-ca',
        'etcd-peer': 'etcd-ca',
        'etcd-server': 'etcd-ca',
        'front-proxy-client': 'front-proxy-ca',
        'scheduler.conf': 'ca',
        'super-admin.conf': 'ca',
    }
    return {
        'kind': 'CertificateExpirationInfo',
        'apiVersion': 'output.kubeadm.k8s.io/v1alpha3',
        'certificates': [
            {
                'name': component,
                'expirationDate': '2030-01-01T00:00:00Z',
                'residualTime': 1000000,
                'externallyManaged': False,
                'caName': issuer,
                'missing': False,
            }
            for component, issuer in families.items()
        ],
        'certificateAuthorities': [
            {
                'name': name,
                'expirationDate': '2036-01-01T00:00:00Z',
                'residualTime': 10000000,
                'externallyManaged': False,
                'missing': False,
            }
            for name in ('ca', 'etcd-ca', 'front-proxy-ca')
        ],
    }


def _prepared_kubeadm_manifest(report: dict, *, cluster_id: str | None = None) -> dict:
    return prepare_kubeadm_metadata_manifest(
        report,
        cluster_id=cluster_id or str(uuid4()),
        node_name='desktop-control-plane',
        source_version='v1.36.4',
        collected_at=datetime.now(UTC).isoformat(),
        reference='UAT-PKI-REPORT-001',
    )


def test_kubeadm_1364_adapter_maps_11_leaf_and_3_ca_metadata_without_raw_fields() -> None:
    manifest = _prepared_kubeadm_manifest(_kubeadm_1364_report())
    assert manifest['schema_version'] == 'kaori.internal-pki-evidence.v1'
    assert manifest['coverage_state'] == 'partial'
    assert len(manifest['certificates']) == 14
    assert sum(item['kind'] == 'leaf' for item in manifest['certificates']) == 11
    assert sum(item['kind'] == 'ca' for item in manifest['certificates']) == 3
    assert all(item['not_before'] is None for item in manifest['certificates'])
    assert all(item['externally_managed'] is False for item in manifest['certificates'])
    assert not any('residualTime' in item or 'missing' in item for item in manifest['certificates'])
    components = {item['component']: item for item in manifest['certificates']}
    assert components['apiserver-etcd-client']['issuer'] == 'etcd-ca'
    assert components['front-proxy-client']['issuer'] == 'front-proxy-ca'
    assert components['apiserver']['not_after'] == '2030-01-01T00:00:00Z'
    assert components['ca']['not_after'] == '2036-01-01T00:00:00Z'


@pytest.mark.parametrize(
    ('change', 'reason'),
    (
        (lambda p: p.update({'privateKey': 'forbidden'}), 'source report fields'),
        (lambda p: p.update({'apiVersion': 'output.kubeadm.k8s.io/v1alpha2'}), 'report schema'),
        (lambda p: p['certificates'][0].update({'privateKey': 'forbidden'}), 'metadata fields'),
        (lambda p: p['certificates'][0].update({'missing': True}), 'Missing'),
        (lambda p: p['certificates'][0].update({'caName': 'unreported-ca'}), 'CA is missing'),
        (lambda p: p['certificates'][0].update({'expirationDate': '2030-01-01'}), 'UTC'),
        (lambda p: p['certificates'].append(dict(p['certificates'][0])), 'Duplicate'),
        (lambda p: p['certificateAuthorities'][0].update({'missing': True}), 'Missing'),
    ),
)
def test_kubeadm_1364_adapter_rejects_unsafe_or_ambiguous_source(change, reason: str) -> None:
    report = _kubeadm_1364_report()
    change(report)
    with pytest.raises(PKIEvidenceValidationError, match=reason):
        _prepared_kubeadm_manifest(report)


def test_kubeadm_1364_adapter_fails_closed_for_unverified_tool_version() -> None:
    with pytest.raises(PKIEvidenceValidationError, match='source version'):
        prepare_kubeadm_metadata_manifest(
            _kubeadm_1364_report(),
            cluster_id=str(uuid4()),
            node_name='desktop-control-plane',
            source_version='v1.35.2',
            collected_at=datetime.now(UTC).isoformat(),
            reference='UAT-PKI-REPORT-001',
        )


def test_prepared_kubeadm_1364_manifest_commits_14_source_qualified_rows(
    pki_repository_app,
) -> None:
    with pki_repository_app.app_context():
        cluster_id = str(uuid4())
        db.session.add(Cluster(id=cluster_id, name='Docker Desktop pilot', environment='non-production'))
        db.session.commit()
        manifest = _prepared_kubeadm_manifest(_kubeadm_1364_report(), cluster_id=cluster_id)
        batch, created = import_attested_pki_metadata(manifest)
        assert created is True
        assert batch.record_count == 14
        assert InternalPKIEvidenceBatch.query.count() == 1
        assert InternalPKICertificateInventory.query.count() == 14
        assert AuditEvent.query.filter_by(action='internal_pki_operator_metadata_import').count() == 1
        inventory = get_internal_certificate_inventory_page({'cluster_id': cluster_id, 'cert_per_page': '5'})
        assert inventory['total'] == 14
        assert inventory['pagination']['per_page'] == 5
        assert inventory['pagination']['total_pages'] == 3
        assert all(row['source_kind'] == 'kubeadm_check_expiration' for row in inventory['records'])

