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
