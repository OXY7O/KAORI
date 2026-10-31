from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from app.extensions.db import db
from app.kubernetes.governance.tls_certificates import service, sync_state
from app.models.cluster import Cluster
from app.models.governance import TLSCertificateCollectionState, TLSCertificateInventory


@pytest.fixture()
def governance_repository_app(monkeypatch: pytest.MonkeyPatch):
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite+pysqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    monkeypatch.setattr(
        service,
        'check_tls_governance_schema_readiness',
        lambda: SimpleNamespace(ready=True, as_dict=lambda: {'ready': True}),
    )
    monkeypatch.setattr(
        sync_state,
        'build_tls_sync_state',
        lambda **_kwargs: {
            'is_active': False,
            'active_job_public_id': None,
            'icon': 'circle-check',
            'label': 'Current',
            'tone': 'normal',
            'progress_message': None,
            'helper': 'Current snapshot.',
            'automatic_enabled': True,
            'last_success_label': 'Now',
            'next_run_label': 'Later',
            'progress_percent': 100,
        },
    )
    with app.app_context():
        Cluster.__table__.create(db.engine)
        TLSCertificateInventory.__table__.create(db.engine)
        TLSCertificateCollectionState.__table__.create(db.engine)
        yield app
        db.session.remove()
        TLSCertificateCollectionState.__table__.drop(db.engine)
        TLSCertificateInventory.__table__.drop(db.engine)
        Cluster.__table__.drop(db.engine)


def test_tls_certificate_page_uses_sql_pagination_and_canonical_page_size(governance_repository_app) -> None:
    now = datetime.now(UTC)
    with governance_repository_app.app_context():
        cluster = Cluster(id='cluster-a', name='Cluster A', environment='production', status='connected')
        db.session.add(cluster)
        db.session.add(
            TLSCertificateCollectionState(
                cluster_id=cluster.id,
                secret_collection_status='collected',
                ingress_mapping_status='collected',
                collected_at=now,
            )
        )
        for index in range(7):
            db.session.add(
                TLSCertificateInventory(
                    cluster_id=cluster.id,
                    namespace='default',
                    secret_name=f'tls-{index}',
                    common_name=f'api-{index}.example.com',
                    issuer='KAORI Test CA',
                    serial_number=str(index),
                    fingerprint_sha256=f'{index:064x}',
                    dns_names=[f'api-{index}.example.com'],
                    ingress_hosts=[f'api-{index}.example.com'],
                    used_by=[],
                    not_before=now - timedelta(days=1),
                    not_after=now + timedelta(days=90 - index),
                    days_remaining=90 - index,
                    status='healthy',
                    risk_level='healthy',
                    coverage_state='full',
                    declared_host_count=1,
                    covered_host_count=1,
                    uncovered_hosts=[],
                    collected_at=now,
                )
            )
        db.session.commit()

        page_two = service.get_tls_certificate_page({'cluster_id': cluster.id, 'page': '2', 'per_page': '5'})
        oversized = service.get_tls_certificate_page({'cluster_id': cluster.id, 'page': '1', 'per_page': '5000'})

        assert page_two['pagination']['total_items'] == 7
        assert page_two['pagination']['per_page'] == 5
        assert len(page_two['records']) == 2
        assert oversized['pagination']['per_page'] == 5
        assert len(oversized['records']) == 5


def test_tls_validity_projection_filters_sorts_and_preserves_committed_facts(governance_repository_app) -> None:
    now = datetime.now(UTC)
    with governance_repository_app.app_context():
        cluster = Cluster(id='as-of-cluster', name='As-of', environment='production', status='connected')
        db.session.add_all(
            [
                cluster,
                TLSCertificateCollectionState(
                    cluster_id=cluster.id,
                    secret_collection_status='collected',
                    ingress_mapping_status='collected',
                    collected_at=now,
                ),
            ]
        )
        entries = (
            ('expired-now', now - timedelta(hours=2), 'healthy', 100),
            ('critical-now', now + timedelta(days=3), 'healthy', 100),
            ('renewal-now', now + timedelta(days=12), 'healthy', 100),
            ('healthy-now', now + timedelta(days=45), 'critical', 2),
            ('parse-invalid', now - timedelta(days=3), 'invalid', None),
            ('parse-unknown', now - timedelta(days=3), 'unknown', None),
        )
        for name, expires_at, stored, days in entries:
            db.session.add(
                TLSCertificateInventory(
                    cluster_id=cluster.id,
                    namespace='default',
                    secret_name=name,
                    status=stored,
                    days_remaining=days,
                    not_after=expires_at,
                    coverage_state='no_declared_hosts',
                    collected_at=now - timedelta(days=2),
                )
            )
        db.session.commit()

        all_rows = service.get_tls_certificate_page({'cluster_id': cluster.id, 'per_page': '50'})
        assert all_rows['summary']['expired'] == 1
        assert all_rows['summary']['critical'] == 1
        assert all_rows['summary']['warning'] == 1
        assert all_rows['summary']['healthy'] == 1
        assert all_rows['summary']['invalid'] == 1
        assert all_rows['summary']['unknown'] == 1
        assert [row.secret_name for row in all_rows['records'][:3]] == [
            'expired-now',
            'parse-invalid',
            'critical-now',
        ]

        for status, expected in (
            ('expired', 'expired-now'),
            ('critical', 'critical-now'),
            ('warning', 'renewal-now'),
            ('healthy', 'healthy-now'),
            ('invalid', 'parse-invalid'),
            ('unknown', 'parse-unknown'),
        ):
            result = service.get_tls_certificate_page({'cluster_id': cluster.id, 'status': status})
            assert [r.secret_name for r in result['records']] == [expected]
            assert result['summary']['total'] == result['pagination']['total_items'] == 1
            assert result['records'][0].presentation['validity_status'] == status
            if status in {'invalid', 'unknown'}:
                assert result['records'][0].presentation['validity_days_remaining'] is None

        source_row = next(r for r in all_rows['records'] if r.secret_name == 'expired-now')
        detail_row = service.get_tls_certificate_detail(source_row.id)
        assert detail_row.presentation['validity_status'] == 'expired'
        assert detail_row.presentation['validity_days_remaining'] <= 0
        assert source_row.status == 'healthy' and source_row.days_remaining == 100
        assert db.session.get(TLSCertificateInventory, source_row.id).status == 'healthy'


def test_failed_tls_secret_sync_does_not_advance_collected_evidence_clock(governance_repository_app) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=5)
    with governance_repository_app.app_context():
        cluster = Cluster(id='freshness-test', name='Freshness', environment='production', status='connected')
        db.session.add(cluster)
        db.session.flush()
        service._persist_collection_state(
            cluster.id,
            secret_status='collected',
            ingress_status='collected',
            secret_detail=None,
            ingress_detail=None,
            collected_at=old,
        )
        db.session.commit()

        service._persist_collection_state(
            cluster.id,
            secret_status='collection_failed',
            ingress_status='collected',
            secret_detail='API failure',
            ingress_detail=None,
            collected_at=now,
        )
        db.session.commit()
        state = db.session.get(TLSCertificateCollectionState, cluster.id)
        assert state.collected_at.replace(tzinfo=UTC) == old
        assert state.secret_collection_status == 'collection_failed'
        assert state.secret_collection_detail == 'API failure'
        assert state.updated_at is not None

        # Complete Secret collection with failed Ingress mapping is a new
        # Secret snapshot but not complete governance coverage.
        service._persist_collection_state(
            cluster.id,
            secret_status='collected',
            ingress_status='permission_unavailable',
            secret_detail=None,
            ingress_detail='Ingress API denied',
            collected_at=now,
        )
        db.session.commit()
        state = db.session.get(TLSCertificateCollectionState, cluster.id)
        assert state.collected_at.replace(tzinfo=UTC) == now
        assert state.ingress_mapping_status == 'permission_unavailable'


def test_incomplete_tls_collection_keeps_last_known_good_inventory(governance_repository_app, monkeypatch) -> None:
    from app.kubernetes.governance.tls_certificates.collector import TLSCollectionBatch, TLSCollectionEvidence

    now = datetime.now(UTC)
    old = now - timedelta(days=3)
    with governance_repository_app.app_context():
        cluster = Cluster(id='failed-collector', name='Failed collector', environment='production', status='connected')
        db.session.add_all(
            [
                cluster,
                TLSCertificateInventory(
                    cluster_id=cluster.id,
                    namespace='default',
                    secret_name='last-good',
                    status='healthy',
                    coverage_state='fully_covered',
                    collected_at=old,
                ),
            ]
        )
        db.session.commit()

        monkeypatch.setattr(
            service,
            'collect_tls_certificate_batch',
            lambda cluster, **kwargs: TLSCollectionBatch(
                records=[],
                evidence=TLSCollectionEvidence(
                    secret_collection_status='collection_failed',
                    ingress_mapping_status='collected',
                    secret_collection_detail='Collection incomplete.',
                ),
                error='Collection incomplete.',
            ),
        )
        result = service.sync_tls_certificates_for_cluster(cluster)
        assert result.fatal_error == 'Collection incomplete.'
        assert result.collected_count == 0
        retained = TLSCertificateInventory.query.filter_by(cluster_id=cluster.id).all()
        assert [row.secret_name for row in retained] == ['last-good']
        assert retained[0].collected_at.replace(tzinfo=UTC) == old
        state = db.session.get(TLSCertificateCollectionState, cluster.id)
        assert state.secret_collection_status == 'collection_failed'
        assert state.collected_at is None


def test_tls_reconciliation_is_bounded_and_prunes_only_successful_generation(
    governance_repository_app,
    monkeypatch,
) -> None:
    from app.kubernetes.governance.tls_certificates.collector import TLSCollectionBatch, TLSCollectionEvidence

    old = datetime.now(UTC) - timedelta(days=4)
    with governance_repository_app.app_context():
        first = Cluster(id='reconcile-a', name='Reconcile A', environment='production', status='connected')
        other = Cluster(id='reconcile-b', name='Reconcile B', environment='production', status='connected')
        db.session.add_all([first, other])
        db.session.flush()
        db.session.add_all(
            [
                TLSCertificateInventory(
                    cluster_id=first.id,
                    namespace='default',
                    secret_name=f'cert-{index:04d}',
                    status='healthy',
                    coverage_state='not_reported',
                    collected_at=old,
                )
                for index in range(230)
            ]
        )
        db.session.add(
            TLSCertificateInventory(
                cluster_id=other.id,
                namespace='default',
                secret_name='must-not-prune',
                status='healthy',
                coverage_state='not_reported',
                collected_at=old,
            )
        )
        db.session.commit()
        preserved = {
            record.secret_name: record.id
            for record in TLSCertificateInventory.query.filter_by(cluster_id=first.id).all()
        }
        payloads = [
            {
                'namespace': 'default',
                'secret_name': f'cert-{index:04d}',
                'status': 'healthy',
                'coverage_state': 'not_reported',
                'collected_at': old,
            }
            for index in range(110, 270)
        ]
        monkeypatch.setattr(
            service,
            'collect_tls_certificate_batch',
            lambda cluster, **kwargs: TLSCollectionBatch(
                records=payloads,
                evidence=TLSCollectionEvidence(
                    secret_collection_status='collected',
                    ingress_mapping_status='collected',
                ),
            ),
        )
        result = service.sync_tls_certificates_for_cluster(first)
        assert result.fatal_error is None
        assert result.collected_count == 160
        actual = TLSCertificateInventory.query.filter_by(cluster_id=first.id).all()
        assert len(actual) == 160
        assert {item.secret_name for item in actual} == {row['secret_name'] for row in payloads}
        assert all(row.collected_at.replace(tzinfo=UTC) > old for row in actual)
        assert all(row.id == preserved[row.secret_name] for row in actual if row.secret_name in preserved)
        assert TLSCertificateInventory.query.filter_by(cluster_id=other.id).count() == 1


def test_tls_reconciliation_zero_records_prunes_only_selected_cluster(governance_repository_app, monkeypatch) -> None:
    from app.kubernetes.governance.tls_certificates.collector import TLSCollectionBatch, TLSCollectionEvidence

    with governance_repository_app.app_context():
        first = Cluster(id='empty-a', name='Empty A', environment='production', status='connected')
        other = Cluster(id='empty-b', name='Empty B', environment='production', status='connected')
        db.session.add_all([first, other])
        db.session.flush()
        for cluster in (first, other):
            db.session.add(
                TLSCertificateInventory(
                    cluster_id=cluster.id,
                    namespace='default',
                    secret_name='old',
                    status='healthy',
                    coverage_state='not_reported',
                )
            )
        db.session.commit()
        monkeypatch.setattr(
            service,
            'collect_tls_certificate_batch',
            lambda cluster, **kwargs: TLSCollectionBatch(
                records=[],
                evidence=TLSCollectionEvidence(
                    secret_collection_status='collected',
                    ingress_mapping_status='collected',
                ),
            ),
        )
        result = service.sync_tls_certificates_for_cluster(first)
        assert result.collected_count == 0
        assert TLSCertificateInventory.query.filter_by(cluster_id=first.id).count() == 0
        assert TLSCertificateInventory.query.filter_by(cluster_id=other.id).count() == 1


def test_tls_duplicate_identity_aborts_reconciliation_without_pruning(
    governance_repository_app,
    monkeypatch,
) -> None:
    from app.kubernetes.governance.tls_certificates.collector import TLSCollectionBatch, TLSCollectionEvidence

    with governance_repository_app.app_context():
        cluster = Cluster(id='duplicate-scope', name='Duplicate', environment='production', status='connected')
        db.session.add(cluster)
        db.session.add(
            TLSCertificateInventory(
                cluster_id=cluster.id,
                namespace='default',
                secret_name='last-good',
                status='healthy',
                coverage_state='not_reported',
            )
        )
        db.session.commit()
        record = {
            'namespace': 'default',
            'secret_name': 'same',
            'status': 'healthy',
            'coverage_state': 'not_reported',
        }
        monkeypatch.setattr(
            service,
            'collect_tls_certificate_batch',
            lambda cluster, **kwargs: TLSCollectionBatch(
                records=[dict(record), dict(record)],
                evidence=TLSCollectionEvidence(
                    secret_collection_status='collected',
                    ingress_mapping_status='collected',
                ),
            ),
        )
        with pytest.raises(ValueError, match='duplicate Secret identities'):
            service.sync_tls_certificates_for_cluster(cluster)
        assert [row.secret_name for row in TLSCertificateInventory.query.filter_by(cluster_id=cluster.id).all()] == [
            'last-good'
        ]
