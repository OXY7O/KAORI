from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from flask import current_app
from sqlalchemy import or_

from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window
from app.integrations.delivery.notification_channels.service import recent_delivery_summary
from app.intelligence.automation_control.notifications import DECISION_NOTIFICATION_EVENTS
from app.intelligence.knowledge.service import custom_runbook_authoring_enabled
from app.intelligence.knowledge.system_catalog import list_system_runbooks
from app.models.intelligence import IntelligenceDecision, IntelligenceDecisionCandidate, IntelligenceExecutionJournal
from app.models.knowledge import KnowledgeRunbook, KnowledgeRunbookAlertBinding, KnowledgeRunbookRevision
from app.models.resolver import ResolverDeploymentPolicy, ResolverOperationalControl, ResolverProductionReadinessRecord

RowPresenter = Callable[[Any], dict[str, Any]]
ScopedRowPresenter = Callable[[Any, Mapping[str, str]], dict[str, Any]]
CatalogBuilder = Callable[[Sequence[Mapping[str, Any]]], list[dict[str, Any]]]


def populate_runbooks_workspace(
    payload: dict[str, Any],
    query_args: Mapping[str, Any],
    registry_rows: Sequence[Mapping[str, Any]],
    *,
    catalog_builder: CatalogBuilder,
    runbook_presenter: RowPresenter,
    binding_presenter: RowPresenter,
) -> None:
    catalog_q = _query_text(query_args, 'catalog_q')
    catalog_status = _query_choice(
        query_args,
        'catalog_status',
        {'all', 'available', 'active', 'catalog_drift', 'resolver_unavailable'},
    )
    catalog_rows = _filter_catalog_rows(catalog_builder(registry_rows), catalog_q, catalog_status)
    payload['system_runbook_catalog'], payload['catalog_pagination'] = _paginate_sequence(
        catalog_rows,
        page=query_args.get('catalog_page', 1),
        per_page=query_args.get('catalog_per_page', 5),
    )

    runbook_q = _query_text(query_args, 'runbook_q')
    runbook_status = _query_choice(query_args, 'runbook_status', {'all', 'active', 'deprecated', 'archived'})
    runbook_query = KnowledgeRunbook.query
    if runbook_q:
        pattern = f'%{runbook_q}%'
        runbook_query = runbook_query.filter(
            or_(KnowledgeRunbook.title.ilike(pattern), KnowledgeRunbook.runbook_key.ilike(pattern))
        )
    if runbook_status != 'all':
        runbook_query = runbook_query.filter(KnowledgeRunbook.lifecycle_status == runbook_status)
    runbook_query = runbook_query.order_by(KnowledgeRunbook.updated_at.desc(), KnowledgeRunbook.id.desc())
    records, payload['runbook_pagination'] = _paginate_query(
        runbook_query,
        page=query_args.get('runbook_page', 1),
        per_page=query_args.get('runbook_per_page', 5),
    )
    payload['runbook_rows'] = [runbook_presenter(record) for record in records]

    binding_q = _query_text(query_args, 'binding_q')
    binding_status = _query_choice(query_args, 'binding_status', {'all', 'active', 'disabled'})
    binding_records, payload['binding_pagination'] = _paginate_query(
        _binding_query(binding_q=binding_q, binding_status=binding_status),
        page=query_args.get('binding_page', 1),
        per_page=query_args.get('binding_per_page', 5),
    )
    payload['binding_rows'] = [binding_presenter(record) for record in binding_records]
    payload['published_revisions'] = _published_system_revisions()
    payload['automation_filters'] = {
        'catalog_q': catalog_q,
        'catalog_status': catalog_status,
        'runbook_q': runbook_q,
        'runbook_status': runbook_status,
        'binding_q': binding_q,
        'binding_status': binding_status,
    }


def populate_decisions_workspace(
    payload: dict[str, Any],
    query_args: Mapping[str, Any],
    cluster_names: Mapping[str, str],
    *,
    candidate_presenter: ScopedRowPresenter,
    decision_presenter: ScopedRowPresenter,
) -> None:
    candidate_q = _query_text(query_args, 'candidate_q')
    candidate_status = _query_choice(
        query_args,
        'candidate_status',
        {'all', 'pending', 'promoted', 'dismissed', 'expired'},
    )
    candidate_records, payload['candidate_pagination'] = _paginate_query(
        _candidate_query(candidate_q=candidate_q, candidate_status=candidate_status),
        page=query_args.get('candidate_page', 1),
        per_page=query_args.get('candidate_per_page', 5),
    )
    payload['candidate_rows'] = [candidate_presenter(record, cluster_names) for record in candidate_records]

    decision_q = _query_text(query_args, 'decision_q')
    decision_status = _query_choice(
        query_args,
        'decision_status',
        {'all', 'ready', 'pending_approval', 'approved', 'rejected', 'expired', 'dispatched'},
    )
    decision_records, payload['decision_pagination'] = _paginate_query(
        _decision_query(decision_q=decision_q, decision_status=decision_status),
        page=query_args.get('decision_page', 1),
        per_page=query_args.get('decision_per_page', 5),
    )
    payload['decision_rows'] = [decision_presenter(record, cluster_names) for record in decision_records]

    delivery_q = _query_text(query_args, 'delivery_q')
    delivery_status = _query_choice(query_args, 'delivery_status', {'all', 'sent', 'failed', 'queued', 'skipped'})
    delivery_rows = _filter_delivery_rows(
        recent_delivery_summary(limit=200, event_types=DECISION_NOTIFICATION_EVENTS),
        query=delivery_q,
        status=delivery_status,
    )
    payload['decision_delivery_rows'], payload['delivery_pagination'] = _paginate_sequence(
        delivery_rows,
        page=query_args.get('delivery_page', 1),
        per_page=query_args.get('delivery_per_page', 5),
    )
    payload['automation_filters'] = {
        'candidate_q': candidate_q,
        'candidate_status': candidate_status,
        'decision_q': decision_q,
        'decision_status': decision_status,
        'delivery_q': delivery_q,
        'delivery_status': delivery_status,
    }


def populate_operations_workspace(
    payload: dict[str, Any],
    query_args: Mapping[str, Any],
    cluster_names: Mapping[str, str],
    *,
    policy_presenter: ScopedRowPresenter,
    journal_presenter: ScopedRowPresenter,
    control_presenter: ScopedRowPresenter,
    metrics_builder: Callable[[], dict[str, int]],
) -> None:
    policy_q = _query_text(query_args, 'policy_q')
    policy_status = _query_choice(query_args, 'policy_status', {'all', 'active', 'disabled'})
    policy_query = ResolverDeploymentPolicy.query
    if policy_q:
        policy_query = policy_query.filter(ResolverDeploymentPolicy.action_key.ilike(f'%{policy_q}%'))
    if policy_status != 'all':
        policy_query = policy_query.filter(ResolverDeploymentPolicy.lifecycle_status == policy_status)
    policy_query = policy_query.order_by(ResolverDeploymentPolicy.updated_at.desc(), ResolverDeploymentPolicy.id.desc())
    policy_records, payload['policy_pagination'] = _paginate_query(
        policy_query,
        page=query_args.get('policy_page', 1),
        per_page=query_args.get('policy_per_page', 5),
    )
    payload['policy_rows'] = [policy_presenter(record, cluster_names) for record in policy_records]

    journal_q = _query_text(query_args, 'journal_q')
    journal_status = _query_choice(
        query_args,
        'journal_status',
        {'all', 'queued', 'running', 'retry_wait', 'completed', 'dead_letter'},
    )
    journal_records, payload['journal_pagination'] = _paginate_query(
        _journal_query(journal_q=journal_q, journal_status=journal_status),
        page=query_args.get('journal_page', 1),
        per_page=query_args.get('journal_per_page', 5),
    )
    payload['journal_rows'] = [journal_presenter(record, cluster_names) for record in journal_records]

    dead_q = _query_text(query_args, 'dead_q')
    dead_records, payload['dead_pagination'] = _paginate_query(
        _journal_query(journal_q=dead_q, journal_status='dead_letter'),
        page=query_args.get('dead_page', 1),
        per_page=query_args.get('dead_per_page', 5),
    )
    payload['dead_letter_rows'] = [journal_presenter(record, cluster_names) for record in dead_records]
    payload['control_rows'] = [
        control_presenter(record, cluster_names)
        for record in ResolverOperationalControl.query.order_by(
            ResolverOperationalControl.cluster_id.asc().nullsfirst(), ResolverOperationalControl.id.asc()
        ).all()
    ]
    payload['metrics'] = metrics_builder()
    payload['automation_filters'] = {
        'policy_q': policy_q,
        'policy_status': policy_status,
        'journal_q': journal_q,
        'journal_status': journal_status,
        'dead_q': dead_q,
    }


def populate_readiness_workspace(
    payload: dict[str, Any],
    query_args: Mapping[str, Any],
    cluster_names: Mapping[str, str],
    *,
    readiness_presenter: ScopedRowPresenter,
) -> None:
    readiness_q = _query_text(query_args, 'readiness_q')
    readiness_stage = _query_choice(
        query_args,
        'readiness_stage',
        {'all', 'disabled', 'shadow', 'non_production', 'canary', 'production'},
    )
    query = ResolverProductionReadinessRecord.query
    if readiness_q:
        query = query.filter(ResolverProductionReadinessRecord.action_key.ilike(f'%{readiness_q}%'))
    if readiness_stage != 'all':
        query = query.filter(ResolverProductionReadinessRecord.rollout_stage == readiness_stage)
    query = query.order_by(
        ResolverProductionReadinessRecord.updated_at.desc(), ResolverProductionReadinessRecord.id.desc()
    )
    records, payload['readiness_pagination'] = _paginate_query(
        query,
        page=query_args.get('readiness_page', 1),
        per_page=query_args.get('readiness_per_page', 5),
    )
    payload['readiness_rows'] = [readiness_presenter(record, cluster_names) for record in records]
    payload['automation_filters'] = {'readiness_q': readiness_q, 'readiness_stage': readiness_stage}


def _filter_catalog_rows(rows: list[dict[str, Any]], query: str, status: str) -> list[dict[str, Any]]:
    if query:
        needle = query.casefold()
        rows = [
            row
            for row in rows
            if needle
            in ' '.join((row['title'], row['key'], row['action_key'], row['domain'], row['asset_kind'])).casefold()
        ]
    if status == 'all':
        return rows
    labels = {
        'available': 'Available',
        'active': 'Active',
        'catalog_drift': 'Catalog Drift',
        'resolver_unavailable': 'Resolver Unavailable',
    }
    return [row for row in rows if row['status'] == labels[status]]


def _binding_query(*, binding_q: str, binding_status: str) -> Any:
    query = KnowledgeRunbookAlertBinding.query
    if binding_q:
        pattern = f'%{binding_q}%'
        query = query.filter(
            or_(
                KnowledgeRunbookAlertBinding.binding_key.ilike(pattern),
                KnowledgeRunbookAlertBinding.rule_key.ilike(pattern),
                KnowledgeRunbookAlertBinding.alertname.ilike(pattern),
                KnowledgeRunbookAlertBinding.namespace.ilike(pattern),
            )
        )
    if binding_status != 'all':
        query = query.filter(KnowledgeRunbookAlertBinding.lifecycle_status == binding_status)
    return query.order_by(KnowledgeRunbookAlertBinding.priority.asc(), KnowledgeRunbookAlertBinding.id.desc())


def _published_system_revisions() -> list[KnowledgeRunbookRevision]:
    query = (
        KnowledgeRunbookRevision.query.join(KnowledgeRunbook)
        .filter(KnowledgeRunbookRevision.publication_status == 'published')
        .order_by(KnowledgeRunbookRevision.published_at.desc(), KnowledgeRunbookRevision.id.desc())
    )
    if not custom_runbook_authoring_enabled(current_app.config):
        system_keys = [item.runbook_key for item in list_system_runbooks()]
        query = query.filter(KnowledgeRunbook.runbook_key.in_(system_keys))
    return list(query.all())


def _candidate_query(*, candidate_q: str, candidate_status: str) -> Any:
    query = IntelligenceDecisionCandidate.query
    if candidate_q:
        pattern = f'%{candidate_q}%'
        query = query.filter(
            or_(
                IntelligenceDecisionCandidate.rule_key.ilike(pattern),
                IntelligenceDecisionCandidate.alert_fingerprint.ilike(pattern),
                IntelligenceDecisionCandidate.namespace.ilike(pattern),
                IntelligenceDecisionCandidate.public_id.ilike(pattern),
            )
        )
    if candidate_status != 'all':
        query = query.filter(IntelligenceDecisionCandidate.review_status == candidate_status)
    return query.order_by(IntelligenceDecisionCandidate.created_at.desc(), IntelligenceDecisionCandidate.id.desc())


def _decision_query(*, decision_q: str, decision_status: str) -> Any:
    query = IntelligenceDecision.query
    if decision_q:
        pattern = f'%{decision_q}%'
        query = query.filter(
            or_(
                IntelligenceDecision.rule_key.ilike(pattern),
                IntelligenceDecision.action_key.ilike(pattern),
                IntelligenceDecision.namespace.ilike(pattern),
                IntelligenceDecision.public_id.ilike(pattern),
            )
        )
    if decision_status != 'all':
        query = query.filter(IntelligenceDecision.workflow_status == decision_status)
    return query.order_by(IntelligenceDecision.created_at.desc(), IntelligenceDecision.id.desc())


def _journal_query(*, journal_q: str, journal_status: str) -> Any:
    query = IntelligenceExecutionJournal.query
    if journal_q:
        pattern = f'%{journal_q}%'
        query = query.filter(
            or_(
                IntelligenceExecutionJournal.action_key.ilike(pattern),
                IntelligenceExecutionJournal.public_id.ilike(pattern),
            )
        )
    if journal_status != 'all':
        query = query.filter(IntelligenceExecutionJournal.orchestration_status == journal_status)
    return query.order_by(IntelligenceExecutionJournal.updated_at.desc(), IntelligenceExecutionJournal.id.desc())


def _filter_delivery_rows(
    rows: Sequence[Mapping[str, Any]], *, query: str, status: str
) -> list[Mapping[str, Any]]:
    filtered = list(rows)
    if query:
        needle = query.casefold()
        filtered = [
            row
            for row in filtered
            if needle
            in ' '.join(
                str(row.get(key) or '') for key in ('event_label', 'channel_name', 'provider', 'asset_key')
            ).casefold()
        ]
    if status != 'all':
        filtered = [row for row in filtered if str(row.get('status') or '') == status]
    return filtered


def _query_text(query_args: Mapping[str, Any], key: str) -> str:
    return str(query_args.get(key) or '').strip()[:200]


def _query_choice(query_args: Mapping[str, Any], key: str, allowed: set[str]) -> str:
    value = str(query_args.get(key) or 'all').strip().lower()
    return value if value in allowed else 'all'


def _paginate_query(query: Any, *, page: Any, per_page: Any) -> tuple[list[Any], dict[str, Any]]:
    window = build_pagination_window(total_items=query.count(), page=page, per_page=per_page)
    rows = query.offset(window.offset).limit(window.per_page).all()
    return rows, {**window.as_dict(), 'allowed_per_page': PER_PAGE_OPTIONS}


def _paginate_sequence(rows: Sequence[Any], *, page: Any, per_page: Any) -> tuple[list[Any], dict[str, Any]]:
    window = build_pagination_window(total_items=len(rows), page=page, per_page=per_page)
    return list(rows[window.offset : window.offset + window.per_page]), {
        **window.as_dict(),
        'allowed_per_page': PER_PAGE_OPTIONS,
    }
