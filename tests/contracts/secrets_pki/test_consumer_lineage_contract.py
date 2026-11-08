"""Typed Secret lineage: no name-only matches, unauthorized link leaks or false blast radius."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.secrets_pki.consumer_lineage import LineageEdge, project_secret_impact


def _id():
    return str(uuid4())


AT = datetime(2026, 10, 22, tzinfo=UTC)


def _edge(kind, source, destination, *, kind_of_resource, status='confirmed', evidence='controller_uid', end=None):
    return LineageEdge(
        edge_id=_id(),
        kind=kind,
        from_id=source,
        to_id=destination,
        resource_kind=kind_of_resource,
        status=status,
        evidence_kind=evidence,
        evidence_id=_id(),
        effective_from=AT - timedelta(days=5),
        effective_until=end,
        observed_at=AT - timedelta(minutes=1),
    )


def _project(secret, edges, consumers, *, source='ready', correlation='ready'):
    return project_secret_impact(
        secret_identity_id=secret,
        edges=tuple(edges),
        authorized_consumer_ids=frozenset(consumers),
        source_freshness=source,
        correlation_freshness=correlation,
        at=AT,
    )


def test_confirmed_two_hop_graph_supports_many_to_many_consumers():
    source = _id()
    materialized = _id()
    c1, c2 = _id(), _id()
    links = [
        _edge('secret_to_materialization', source, materialized, kind_of_resource='kubernetes_secret'),
        _edge('materialization_to_consumer', materialized, c1, kind_of_resource='kubernetes_workload'),
        _edge(
            'materialization_to_consumer',
            materialized,
            c2,
            kind_of_resource='service_environment',
            evidence='runtime_readback',
        ),
    ]
    impact = _project(source, links, {c1, c2})
    assert impact.state == 'qualified_current'
    assert impact.matching_materializations == 1
    assert set(impact.confirmed_consumers) == {c1, c2}
    assert 'secret_path' not in impact.__dataclass_fields__


def test_approved_declarations_are_candidates_not_confirmed_usage():
    source, materialized, consumer = _id(), _id(), _id()
    with pytest.raises(ValueError, match='mapping alone'):
        _edge(
            'secret_to_materialization',
            source,
            materialized,
            kind_of_resource='csi_volume',
            evidence='approved_mapping',
        )
    source_link = _edge(
        'secret_to_materialization',
        source,
        materialized,
        kind_of_resource='csi_volume',
        status='candidate',
        evidence='approved_mapping',
    )
    consumer_link = _edge(
        'materialization_to_consumer',
        materialized,
        consumer,
        kind_of_resource='kubernetes_workload',
        status='candidate',
        evidence='approved_mapping',
    )
    result = _project(source, [source_link, consumer_link], {consumer})
    assert result.confirmed_consumers == ()
    assert result.state == 'not_proven'


def test_ambiguous_or_conflicted_edges_are_excluded_not_silently_resolved():
    source, materialized, consumer = _id(), _id(), _id()
    evidence = [
        _edge('secret_to_materialization', source, materialized, kind_of_resource='kubernetes_secret'),
        _edge('materialization_to_consumer', materialized, consumer, kind_of_resource='kubernetes_workload'),
        _edge(
            'materialization_to_consumer',
            materialized,
            consumer,
            kind_of_resource='kubernetes_workload',
            status='conflict',
        ),
    ]
    impact = _project(source, evidence, {consumer})
    assert impact.state == 'not_proven'
    assert impact.confirmed_consumers == ()


def test_retired_edge_and_unauthorized_consumer_do_not_leak():
    source, mat, consumer = _id(), _id(), _id()
    historic = _edge(
        'secret_to_materialization', source, mat, kind_of_resource='vault_agent_template', end=AT - timedelta(days=1)
    )
    usage = _edge('materialization_to_consumer', mat, consumer, kind_of_resource='ci_pipeline')
    impact = _project(source, [historic, usage], {consumer})
    assert impact.confirmed_consumers == ()
    active = replace(historic, effective_until=None)
    assert _project(source, [active, usage], set()).confirmed_consumers == ()


def test_provider_or_correlation_outage_downgrades_current_impact():
    source, mat, consumer = _id(), _id(), _id()
    graph = [
        _edge('secret_to_materialization', source, mat, kind_of_resource='injection_session'),
        _edge('materialization_to_consumer', mat, consumer, kind_of_resource='automation_runner'),
    ]
    for source_state, correlation_state in [
        ('stale', 'ready'),
        ('ready', 'partial'),
        ('ready', 'not_collected'),
    ]:
        impact = _project(source, graph, {consumer}, source=source_state, correlation=correlation_state)
        assert impact.state == 'historical_only'
        assert impact.confirmed_consumers == (consumer,)


def test_raw_paths_are_not_valid_identities_and_source_scope_is_bounded():
    with pytest.raises(ValueError, match='UUID'):
        _project('team/db/production', [], set())
    with pytest.raises(ValueError, match='bounded'):
        _project(_id(), [], {_id() for _ in range(501)})


def test_typing_and_evidence_sources_fail_closed():
    with pytest.raises(ValueError, match='typed materialization'):
        _edge('secret_to_materialization', _id(), _id(), kind_of_resource='kubernetes_workload')
    with pytest.raises(ValueError, match='Unsupported lineage'):
        _edge(
            'materialization_to_consumer',
            _id(),
            _id(),
            kind_of_resource='ci_pipeline',
            status='candidate',
            evidence='matching_path',
        )
