from __future__ import annotations

from app.analytics.kubernetes.materialization.requests import choose_cluster_reference
from app.analytics.kubernetes.materialization.serialization import ClusterReference, decode_value, encode_value


def _cluster(cluster_id: str, name: str) -> ClusterReference:
    return ClusterReference(
        id=cluster_id,
        name=name,
        environment='development',
        status='connected',
    )


def test_default_cluster_prefers_analytics_ready_scope() -> None:
    cluster_a = _cluster('cluster-a', 'Cluster A')
    cluster_b = _cluster('cluster-b', 'Cluster B')

    selected = choose_cluster_reference(
        raw_cluster_id='',
        clusters=[cluster_a, cluster_b],
        is_analytics_ready=lambda cluster_id: cluster_id == 'cluster-b',
    )

    assert selected == cluster_b


def test_explicit_unready_cluster_remains_authoritative() -> None:
    cluster_a = _cluster('cluster-a', 'Cluster A')
    cluster_b = _cluster('cluster-b', 'Cluster B')

    selected = choose_cluster_reference(
        raw_cluster_id='cluster-a',
        clusters=[cluster_a, cluster_b],
        is_analytics_ready=lambda cluster_id: cluster_id == 'cluster-b',
    )

    assert selected == cluster_a


def test_cluster_snapshot_round_trip_never_returns_orm_entity() -> None:
    original = _cluster('cluster-b', 'Cluster B')

    decoded = decode_value(encode_value(original))

    assert isinstance(decoded, ClusterReference)
    assert decoded.id == 'cluster-b'
    assert decoded.name == 'Cluster B'
    assert decoded.environment == 'development'
