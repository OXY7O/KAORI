from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from flask import current_app

from app.automation_control.notifications import DECISION_NOTIFICATION_EVENTS
from app.automation_control.overview import build_automation_overview
from app.common.automation_execution import execution_enabled
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window
from app.common.presentation import present_key_label, present_user_datetime
from app.extensions.db import db
from app.integrations.resolver_bootstrap import SUPPORTED_RESOLVER_ACTIONS, get_resolver_registry
from app.knowledge.service import custom_runbook_authoring_enabled
from app.knowledge.system_catalog import is_system_runbook_key, list_system_runbooks
from app.models.audit import AuditEvent
from app.models.cluster import Cluster
from app.models.intelligence import (
    IntelligenceDecision,
    IntelligenceDecisionCandidate,
    IntelligenceExecutionJournal,
)
from app.models.knowledge import (
    KnowledgeRunbook,
    KnowledgeRunbookAlertBinding,
    KnowledgeRunbookRevision,
)
from app.models.resolver import (
    ResolverDeploymentPolicy,
    ResolverOperationalControl,
    ResolverProductionReadinessRecord,
)
from app.notification_channels.service import list_event_channel_options, recent_delivery_summary
from app.resolver.production_readiness import REQUIRED_CHECKS, STAGE_ORDER, assess_readiness

WORKSPACE_KEYS = ('overview', 'runbooks', 'decisions', 'operations', 'readiness')


def build_automation_control_context(query_args: Mapping[str, Any]) -> dict[str, Any]:
    workspace = str(query_args.get('workspace') or 'overview').strip().lower()
    if workspace not in WORKSPACE_KEYS:
        workspace = 'overview'
    page = query_args.get('page', 1)
    per_page = query_args.get('per_page', 5)

    clusters = Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
    cluster_names = {str(cluster.id): cluster.name for cluster in clusters}
    registry_rows, registry_fingerprint = _registry_rows()

    infrastructure_execution_enabled = execution_enabled()
    overview_state = build_automation_overview(
        execution_enabled=infrastructure_execution_enabled,
        registry_rows=registry_rows,
    )
    counts = {
        'runbooks': KnowledgeRunbook.query.count(),
        'published_revisions': KnowledgeRunbookRevision.query.filter_by(publication_status='published').count(),
        'pending_candidates': IntelligenceDecisionCandidate.query.filter_by(review_status='pending').count(),
        'pending_decisions': IntelligenceDecision.query.filter(
            IntelligenceDecision.workflow_status.in_(('ready', 'pending_approval', 'approved'))
        ).count(),
        'dead_letters': IntelligenceExecutionJournal.query.filter_by(orchestration_status='dead_letter').count(),
        'readiness_records': ResolverProductionReadinessRecord.query.count(),
        **overview_state['counts'],
    }

    workspace_rows = _workspace_rows(workspace)
    payload: dict[str, Any] = {
        'workspace': workspace,
        'workspaces': workspace_rows,
        'workspace_tabs': _workspace_tabs(),
        'active_workspace': next(item for item in workspace_rows if item['active']),
        'execution_enabled': infrastructure_execution_enabled,
        'posture': overview_state['posture'],
        'overview_state': overview_state,
        'counts': counts,
        'clusters': clusters,
        'cluster_names': cluster_names,
        'registry_rows': registry_rows,
        'registry_fingerprint': registry_fingerprint,
        'required_checks': REQUIRED_CHECKS,
        'stage_order': STAGE_ORDER,
        'per_page_options': PER_PAGE_OPTIONS,
        'global_control': ResolverOperationalControl.query.filter_by(cluster_id=None).one_or_none(),
        'system_runbook_catalog': [],
        'custom_runbook_authoring_enabled': custom_runbook_authoring_enabled(current_app.config),
        'runbook_rows': [],
        'revision_rows': [],
        'binding_rows': [],
        'candidate_rows': [],
        'decision_rows': [],
        'decision_notification': _decision_notification_context(),
        'decision_delivery_rows': [],
        'journal_rows': [],
        'dead_letter_rows': [],
        'policy_rows': [],
        'control_rows': [],
        'readiness_rows': [],
        'pagination': None,
        'resource_label': 'items',
    }

    if workspace == 'overview':
        payload.update(_overview_activity(cluster_names))
    elif workspace == 'runbooks':
        payload['system_runbook_catalog'] = _system_runbook_catalog_rows(registry_rows)
        query = KnowledgeRunbook.query.order_by(KnowledgeRunbook.updated_at.desc(), KnowledgeRunbook.id.desc())
        records, pagination = _paginate_query(query, page=page, per_page=per_page)
        payload['runbook_rows'] = [_runbook_row(record) for record in records]
        payload['revision_rows'] = [
            _revision_row(record)
            for record in KnowledgeRunbookRevision.query.order_by(
                KnowledgeRunbookRevision.created_at.desc(), KnowledgeRunbookRevision.id.desc()
            )
            .limit(10)
            .all()
        ]
        payload['binding_rows'] = [
            _binding_row(record)
            for record in KnowledgeRunbookAlertBinding.query.order_by(
                KnowledgeRunbookAlertBinding.priority.asc(), KnowledgeRunbookAlertBinding.id.desc()
            )
            .limit(10)
            .all()
        ]
        published_query = (
            KnowledgeRunbookRevision.query.join(KnowledgeRunbook)
            .filter(KnowledgeRunbookRevision.publication_status == 'published')
            .order_by(KnowledgeRunbookRevision.published_at.desc(), KnowledgeRunbookRevision.id.desc())
        )
        if not payload['custom_runbook_authoring_enabled']:
            system_keys = [item.runbook_key for item in list_system_runbooks()]
            published_query = published_query.filter(KnowledgeRunbook.runbook_key.in_(system_keys))
        payload['published_revisions'] = published_query.all()
        payload['pagination'] = pagination
        payload['resource_label'] = 'runbooks'
    elif workspace == 'decisions':
        query = IntelligenceDecisionCandidate.query.order_by(
            IntelligenceDecisionCandidate.created_at.desc(), IntelligenceDecisionCandidate.id.desc()
        )
        records, pagination = _paginate_query(query, page=page, per_page=per_page)
        payload['candidate_rows'] = [_candidate_row(record, cluster_names) for record in records]
        payload['decision_rows'] = [
            _decision_row(record, cluster_names)
            for record in IntelligenceDecision.query.order_by(
                IntelligenceDecision.created_at.desc(), IntelligenceDecision.id.desc()
            )
            .limit(10)
            .all()
        ]
        payload['decision_delivery_rows'] = recent_delivery_summary(
            limit=8,
            event_types=DECISION_NOTIFICATION_EVENTS,
        )
        payload['pagination'] = pagination
        payload['resource_label'] = 'candidates'
    elif workspace == 'operations':
        query = ResolverDeploymentPolicy.query.order_by(
            ResolverDeploymentPolicy.updated_at.desc(), ResolverDeploymentPolicy.id.desc()
        )
        records, pagination = _paginate_query(query, page=page, per_page=per_page)
        payload['policy_rows'] = [_policy_row(record, cluster_names) for record in records]
        payload['control_rows'] = [
            _control_row(record, cluster_names)
            for record in ResolverOperationalControl.query.order_by(
                ResolverOperationalControl.cluster_id.asc().nullsfirst(), ResolverOperationalControl.id.asc()
            ).all()
        ]
        payload['journal_rows'] = [
            _journal_row(record, cluster_names)
            for record in IntelligenceExecutionJournal.query.order_by(
                IntelligenceExecutionJournal.updated_at.desc(), IntelligenceExecutionJournal.id.desc()
            ).limit(10).all()
        ]
        payload['dead_letter_rows'] = [
            _journal_row(record, cluster_names)
            for record in IntelligenceExecutionJournal.query.filter_by(orchestration_status='dead_letter')
            .order_by(IntelligenceExecutionJournal.updated_at.desc(), IntelligenceExecutionJournal.id.desc())
            .limit(10)
            .all()
        ]
        payload['metrics'] = _resolver_metrics()
        payload['pagination'] = pagination
        payload['resource_label'] = 'deployment policies'
    else:
        query = ResolverProductionReadinessRecord.query.order_by(
            ResolverProductionReadinessRecord.updated_at.desc(), ResolverProductionReadinessRecord.id.desc()
        )
        records, pagination = _paginate_query(query, page=page, per_page=per_page)
        payload['readiness_rows'] = [_readiness_row(record, cluster_names) for record in records]
        payload['pagination'] = pagination
        payload['resource_label'] = 'readiness records'

    return payload


def _overview_activity(cluster_names: Mapping[str, str]) -> dict[str, Any]:
    candidates = IntelligenceDecisionCandidate.query.order_by(
        IntelligenceDecisionCandidate.created_at.desc(), IntelligenceDecisionCandidate.id.desc()
    ).limit(5).all()
    decisions = IntelligenceDecision.query.order_by(
        IntelligenceDecision.created_at.desc(), IntelligenceDecision.id.desc()
    ).limit(5).all()
    journals = IntelligenceExecutionJournal.query.order_by(
        IntelligenceExecutionJournal.updated_at.desc(), IntelligenceExecutionJournal.id.desc()
    ).limit(5).all()
    return {
        'candidate_rows': [_candidate_row(record, cluster_names) for record in candidates],
        'decision_rows': [_decision_row(record, cluster_names) for record in decisions],
        'journal_rows': [_journal_row(record, cluster_names) for record in journals],
        'pagination': None,
        'resource_label': 'automation activity',
    }


def upsert_deployment_policy(
    *,
    cluster_id: str,
    action_key: str,
    lifecycle_status: str,
    allowed_namespaces: Sequence[str],
    required_registry_fingerprint: str | None,
    actor_user_id: int | None,
) -> ResolverDeploymentPolicy:
    if lifecycle_status not in {'active', 'disabled'}:
        raise ValueError('Deployment policy status must be active or disabled.')
    cluster = db.session.get(Cluster, cluster_id)
    if cluster is None:
        raise ValueError('Selected cluster does not exist.')
    registry = get_resolver_registry(current_app)
    registry.describe(action_key)
    current_fingerprint = str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or '').strip()
    requested_fingerprint = str(required_registry_fingerprint or '').strip()
    if requested_fingerprint and requested_fingerprint != current_fingerprint:
        raise ValueError('Required registry fingerprint does not match the current KAORI resolver registry.')
    pinned_fingerprint = requested_fingerprint or current_fingerprint or None
    namespaces = sorted({item.strip() for item in allowed_namespaces if item.strip()})
    if lifecycle_status == 'active' and not namespaces:
        raise ValueError('An active resolver deployment policy requires an explicit namespace allowlist.')

    record = ResolverDeploymentPolicy.query.filter_by(cluster_id=cluster_id, action_key=action_key).one_or_none()
    created = record is None
    if record is None:
        record = ResolverDeploymentPolicy()
        record.cluster_id = cluster_id
        record.action_key = action_key
        record.created_by_user_id = actor_user_id
        db.session.add(record)
    record.lifecycle_status = lifecycle_status
    record.allowed_namespaces_json = namespaces
    record.required_registry_fingerprint = pinned_fingerprint
    record.updated_by_user_id = actor_user_id

    event = AuditEvent()
    event.actor_user_id = actor_user_id
    event.target_type = 'resolver_deployment_policy'
    event.target_id = f'{cluster_id}:{action_key}'
    event.action = 'resolver.deployment_policy.created' if created else 'resolver.deployment_policy.updated'
    event.summary = 'KAORI resolver deployment policy updated.'
    event.metadata_json = {
        'cluster_id': cluster_id,
        'action_key': action_key,
        'lifecycle_status': lifecycle_status,
        'allowed_namespaces': namespaces,
        'required_registry_fingerprint': record.required_registry_fingerprint,
    }
    db.session.add(event)
    db.session.commit()
    return record


def _workspace_tabs() -> list[dict[str, str]]:
    definitions = (
        ('overview', 'Overview', 'layout-dashboard'),
        ('runbooks', 'Runbooks & Bindings', 'book-open-check'),
        ('decisions', 'Decision Review', 'clipboard-check'),
        ('operations', 'Execution Control', 'server-cog'),
        ('readiness', 'Production Readiness', 'shield-check'),
    )
    from flask import url_for

    return [
        {'key': key, 'label': label, 'icon': icon, 'href': url_for('automation_control.index', workspace=key)}
        for key, label, icon in definitions
    ]


def _workspace_rows(active: str) -> list[dict[str, str | bool]]:
    definitions = (
        ('overview', 'Overview', 'layout-dashboard', 'Review decision flow, execution posture, safety controls, and delivery readiness.'),
        (
            'runbooks',
            'Runbooks & Bindings',
            'book-open-check',
            'Review immutable runbooks, alert bindings, resolver actions, and execution eligibility.',
        ),
        ('decisions', 'Decision Review', 'clipboard-check', 'Review candidates, immutable decisions, approval requirements, scope, and expiry.'),
        (
            'operations',
            'Execution Control',
            'server-cog',
            'Review resolver registry, deployment policy, safety controls, execution journals, and dead letters.',
        ),
        ('readiness', 'Production Readiness', 'shield-check', 'Record evidence and advance staged rollout.'),
    )
    return [
        {'key': key, 'label': label, 'icon': icon, 'description': description, 'active': key == active}
        for key, label, icon, description in definitions
    ]


def _registry_rows() -> tuple[list[dict[str, Any]], str]:
    try:
        registry = get_resolver_registry(current_app)
    except Exception:
        return [], str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or '')
    rows = []
    for action_key in registry.registered_actions():
        descriptor = registry.describe(action_key)
        rows.append(
            {
                'action_key': descriptor.action_key,
                'capabilities': list(descriptor.capability_keys),
                'profiles': list(descriptor.compatibility_profiles),
                'rollback_required': descriptor.rollback_required,
                'verification_required': descriptor.verification_required,
            }
        )
    return rows, str(current_app.config.get('RESOLVER_REGISTRY_FINGERPRINT') or '')


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



def _system_runbook_catalog_rows(registry_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    registry_actions = {str(row.get('action_key') or '') for row in registry_rows}
    rows: list[dict[str, Any]] = []
    for definition in list_system_runbooks():
        runbook = KnowledgeRunbook.query.filter_by(runbook_key=definition.runbook_key).one_or_none()
        revision = None
        binding_count = 0
        if runbook is not None:
            revision = KnowledgeRunbookRevision.query.filter_by(
                runbook_id=runbook.id,
                version=definition.version,
            ).one_or_none()
            if revision is not None:
                binding_count = KnowledgeRunbookAlertBinding.query.filter_by(
                    runbook_revision_id=revision.id,
                    lifecycle_status='active',
                ).count()

        resolver_available = definition.action_key in SUPPORTED_RESOLVER_ACTIONS
        execution_registered = definition.action_key in registry_actions
        catalog_drift = bool(revision is not None and revision.content_hash != definition.content_hash)
        activated = bool(
            revision is not None
            and revision.publication_status == 'published'
            and not catalog_drift
        )
        if catalog_drift:
            status = 'Catalog Drift'
            tone = 'critical'
        elif activated:
            status = 'Active'
            tone = 'normal'
        elif not resolver_available:
            status = 'Resolver Unavailable'
            tone = 'warning'
        else:
            status = 'Available'
            tone = 'info'

        rows.append(
            {
                'key': definition.runbook_key,
                'title': definition.title,
                'description': definition.description,
                'domain': definition.domain,
                'asset_kind': definition.asset_kind,
                'version': definition.version,
                'action_key': definition.action_key,
                'approval_policy': definition.approval_policy,
                'maturity': definition.maturity,
                'validation_status': definition.validation_status,
                'verification_summary': definition.verification_summary,
                'recovery_summary': definition.recovery_summary,
                'required_evidence': list(definition.required_evidence),
                'required_capabilities': list(definition.required_capabilities),
                'compatibility_profiles': list(definition.compatibility_profiles),
                'default_evidence_mapping': dict(definition.default_evidence_mapping),
                'content_hash': definition.content_hash,
                'resolver_available': resolver_available,
                'execution_registered': execution_registered,
                'activated': activated,
                'catalog_drift': catalog_drift,
                'binding_count': binding_count,
                'status': status,
                'tone': tone,
            }
        )
    return rows


def _runbook_row(record: KnowledgeRunbook) -> dict[str, Any]:
    revisions = list(record.revisions or [])
    published = [item for item in revisions if item.publication_status == 'published']
    revision_ids = [item.id for item in revisions]
    binding_count = (
        KnowledgeRunbookAlertBinding.query.filter(
            KnowledgeRunbookAlertBinding.runbook_revision_id.in_(revision_ids),
            KnowledgeRunbookAlertBinding.lifecycle_status == 'active',
        ).count()
        if revision_ids
        else 0
    )
    latest_published = max(published, key=lambda item: item.published_at or item.created_at) if published else None
    return {
        'id': record.id,
        'key': record.runbook_key,
        'title': record.title,
        'description': record.description or 'No description recorded.',
        'source': 'system' if is_system_runbook_key(record.runbook_key) else 'custom',
        'status': record.lifecycle_status,
        'revision_count': len(revisions),
        'published_count': len(published),
        'binding_count': binding_count,
        'latest_published_version': latest_published.version if latest_published else '-',
        'updated_at': present_user_datetime(record.updated_at),
    }


def _revision_row(record: KnowledgeRunbookRevision) -> dict[str, Any]:
    validation = record.publication_validation_json or {}
    execution_modes = {
        'blocked': ('Advisory Only', 'unknown'),
        'needs_approval': ('Approval Required', 'warning'),
        'allowed': ('Policy Eligible', 'info'),
    }
    execution_mode, execution_tone = execution_modes.get(record.approval_policy, ('Unknown', 'unknown'))
    return {
        'id': record.id,
        'runbook_key': record.runbook.runbook_key,
        'version': record.version,
        'action_key': record.action_key,
        'resolver_key': record.resolver_key,
        'status': record.publication_status,
        'approval_policy': record.approval_policy,
        'execution_mode': execution_mode,
        'execution_tone': execution_tone,
        'rollback_defined': bool(record.rollback_json),
        'validation_valid': validation.get('valid'),
        'validation_errors': list(validation.get('errors') or []),
        'created_at': present_user_datetime(record.created_at),
    }


def _binding_row(record: KnowledgeRunbookAlertBinding) -> dict[str, Any]:
    return {
        'id': record.id,
        'binding_key': record.binding_key,
        'runbook_key': record.revision.runbook.runbook_key,
        'version': record.revision.version,
        'selector': record.rule_key or record.alertname or '-',
        'cluster_id': record.cluster_id or 'All clusters',
        'namespace': record.namespace or 'All namespaces',
        'priority': record.priority,
        'status': record.lifecycle_status,
    }


def _candidate_row(record: IntelligenceDecisionCandidate, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    candidate = record.candidate_json or {}
    return {
        'id': record.id,
        'public_id': record.public_id,
        'rule_key': record.rule_key or candidate.get('rule_key') or '-',
        'action_key': candidate.get('action_key') or '-',
        'runbook_key': candidate.get('runbook_key') or '-',
        'runbook_version': candidate.get('runbook_version') or '-',
        'approval_policy': candidate.get('approval_policy') or 'unknown',
        'resolver_key': candidate.get('resolver_key') or '-',
        'cluster': cluster_names.get(str(record.cluster_id), record.cluster_id or 'Global'),
        'namespace': record.namespace or 'All namespaces',
        'severity': record.severity,
        'status': record.review_status,
        'expires_at': present_user_datetime(record.expires_at),
        'created_at': present_user_datetime(record.created_at),
    }


def _decision_row(record: IntelligenceDecision, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    approval = record.approvals[0] if record.approvals else None
    return {
        'id': record.id,
        'public_id': record.public_id,
        'rule_key': record.rule_key,
        'action_key': record.action_key,
        'runbook_key': record.runbook_key or '-',
        'cluster': cluster_names.get(str(record.cluster_id), record.cluster_id or 'Global'),
        'namespace': record.namespace or 'All namespaces',
        'severity': record.severity,
        'policy': record.policy_outcome,
        'policy_reason': record.policy_reason,
        'approval_required': record.approval_required,
        'created_by_user_id': record.created_by_user_id,
        'approval_outcome': approval.outcome if approval else None,
        'approval_reason': approval.reason if approval and approval.reason else '-',
        'approval_actor': approval.actor.display_label if approval and approval.actor else '-',
        'approval_at': present_user_datetime(approval.created_at, empty='-') if approval else '-',
        'status': record.workflow_status,
        'evidence_hash': record.evidence_hash,
        'expires_at': present_user_datetime(record.expires_at),
    }


def _decision_notification_context() -> dict[str, Any]:
    approval_required = list_event_channel_options(
        event_type='automation.approval_required',
        domain='kubernetes',
    )
    approved = list_event_channel_options(
        event_type='automation.decision_approved',
        domain='kubernetes',
    )
    rejected = list_event_channel_options(
        event_type='automation.decision_rejected',
        domain='kubernetes',
    )
    return {
        'approval_required': _channel_posture(approval_required),
        'approved': _channel_posture(approved),
        'rejected': _channel_posture(rejected),
    }


def _channel_posture(options: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [item for item in options if item.get('selectable')]
    if eligible:
        label, tone = 'Ready', 'normal'
        helper = f'{len(eligible)} validated channel(s) allow this Automation Control event.'
    elif options:
        label, tone = 'Configuration Required', 'warning'
        helper = 'Configured channels exist, but none is currently validated and eligible for this event.'
    else:
        label, tone = 'Not Configured', 'unknown'
        helper = 'No Notification Channel currently allows this Automation Control event.'
    return {
        'label': label,
        'tone': tone,
        'helper': helper,
        'eligible': len(eligible),
        'total': len(options),
        'channels': list(options),
    }


def _journal_row(record: IntelligenceExecutionJournal, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    decision = record.decision
    verification = dict((record.result_json or {}).get('verification') or {})
    dry_run = dict((record.result_json or {}).get('dry_run') or {})
    return {
        'id': record.id,
        'public_id': record.public_id,
        'action_key': record.action_key,
        'cluster': cluster_names.get(str(decision.cluster_id), decision.cluster_id or 'Global'),
        'namespace': decision.namespace or 'All namespaces',
        'status': record.status,
        'orchestration_status': record.orchestration_status,
        'verification_status': str(verification.get('status') or 'not_started'),
        'verification_summary': str(verification.get('summary') or '-'),
        'dry_run_allowed': dry_run.get('allowed'),
        'recovery_mode': str((dry_run.get('rollback_plan') or {}).get('mode') or '-'),
        'attempts': f'{record.attempt_count}/{record.max_attempts}',
        'error': record.error_message or record.last_error_code or '-',
        'updated_at': present_user_datetime(record.updated_at),
    }


def _policy_row(record: ResolverDeploymentPolicy, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    return {
        'id': record.id,
        'cluster_id': record.cluster_id,
        'cluster': cluster_names.get(str(record.cluster_id), record.cluster_id),
        'action_key': record.action_key,
        'status': record.lifecycle_status,
        'namespaces': list(record.allowed_namespaces_json or []),
        'fingerprint': record.required_registry_fingerprint or 'Current process registry',
        'updated_at': present_user_datetime(record.updated_at),
    }


def _control_row(record: ResolverOperationalControl, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    return {
        'id': record.id,
        'cluster_id': record.cluster_id or '',
        'scope': cluster_names.get(str(record.cluster_id), record.cluster_id) if record.cluster_id else 'Global',
        'kill_switch': record.global_kill_switch,
        'maintenance_mode': record.maintenance_mode,
        'concurrency_limit': record.concurrency_limit,
        'rate_limit': record.rate_limit_per_minute,
        'failure_threshold': record.circuit_failure_threshold,
        'cooldown_seconds': record.circuit_cooldown_seconds,
        'circuit_open_until': present_user_datetime(record.circuit_open_until, empty='Closed'),
        'updated_at': present_user_datetime(record.updated_at),
    }


def _readiness_row(record: ResolverProductionReadinessRecord, cluster_names: Mapping[str, str]) -> dict[str, Any]:
    try:
        assessment = assess_readiness(results=record.validation_results_json, rollout_stage=record.rollout_stage)
        failed_checks = list(assessment.failed_checks)
        ready = assessment.ready
    except Exception as exc:
        failed_checks = [str(exc)]
        ready = False
    completed = sum(1 for key in REQUIRED_CHECKS if record.validation_results_json.get(key) is True)
    return {
        'id': record.id,
        'cluster_id': record.cluster_id,
        'cluster': cluster_names.get(str(record.cluster_id), record.cluster_id),
        'action_key': record.action_key,
        'stage': record.rollout_stage,
        'ready': ready,
        'completed_checks': completed,
        'total_checks': len(REQUIRED_CHECKS),
        'failed_checks': failed_checks,
        'evidence_hash': record.evidence_hash or '-',
        'validated_at': present_user_datetime(record.validated_at, empty='Not validated'),
        'approved_at': present_user_datetime(record.approved_at, empty='Not approved'),
    }


def _resolver_metrics() -> dict[str, int]:
    statuses = dict(
        db.session.query(
            IntelligenceExecutionJournal.orchestration_status,
            db.func.count(IntelligenceExecutionJournal.id),
        )
        .group_by(IntelligenceExecutionJournal.orchestration_status)
        .all()
    )
    return {
        'queued': int(statuses.get('queued', 0)),
        'running': int(statuses.get('running', 0)),
        'retry_wait': int(statuses.get('retry_wait', 0)),
        'completed': int(statuses.get('completed', 0)),
        'dead_letter': int(statuses.get('dead_letter', 0)),
    }


def status_label(value: str | None) -> str:
    return present_key_label(value, empty='Unknown')
