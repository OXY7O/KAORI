from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from flask import current_app
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.governance.tls_certificates.certificate import (
    find_uncovered_hosts,
    matching_certificate_pattern,
    validate_certificate_pair,
    validity_policy_from_config,
)
from app.kubernetes.governance.tls_certificates.constants import (
    TLS_COLLECTION_COLLECTED,
    TLS_COVERAGE_FULL,
    TLS_COVERAGE_NONE,
    TLS_COVERAGE_NOT_REPORTED,
    TLS_COVERAGE_PARTIAL,
    TLS_COVERAGE_UNCOVERED,
)
from app.kubernetes.governance.tls_certificates.mutation import (
    TLSSecretIdentityError,
    patch_tls_secret,
    preflight_tls_secret,
    read_uploaded_pair,
)
from app.kubernetes.governance.tls_certificates.sync_state import (
    tls_sync_evidence_is_current,
    tls_sync_stale_after,
)
from app.models import (
    TLSCertificateCollectionState,
    TLSCertificateInventory,
    TLSCertificateUpdateEvent,
    User,
)
from app.platform_operations.jobs.policies.service import get_or_create_job_policy


@dataclass(frozen=True)
class TLSUpdateTarget:
    id: int
    cluster_id: str
    cluster_name: str
    namespace: str
    secret_name: str
    not_after: datetime | None


def _target_view(record: TLSCertificateInventory) -> TLSUpdateTarget:
    cluster = getattr(record, 'cluster', None)
    return TLSUpdateTarget(
        id=int(record.id),
        cluster_id=str(record.cluster_id),
        cluster_name=str(getattr(cluster, 'name', None) or record.cluster_id),
        namespace=str(record.namespace),
        secret_name=str(record.secret_name),
        not_after=record.not_after,
    )


@dataclass(frozen=True)
class TLSUpdateEventSpec:
    cluster_id: str
    namespace: str
    secret_name: str
    old_fingerprint_sha256: str | None
    new_fingerprint_sha256: str | None
    old_not_after: datetime | None
    new_not_after: datetime | None
    status: str
    message: str | None
    actor_user_id: int | None
    bulk_job_id: str | None = None


def _new_tls_update_event(spec: TLSUpdateEventSpec) -> TLSCertificateUpdateEvent:
    event = TLSCertificateUpdateEvent()
    event.cluster_id = spec.cluster_id
    event.namespace = spec.namespace
    event.secret_name = spec.secret_name
    event.old_fingerprint_sha256 = spec.old_fingerprint_sha256
    event.new_fingerprint_sha256 = spec.new_fingerprint_sha256
    event.old_not_after = spec.old_not_after
    event.new_not_after = spec.new_not_after
    event.status = spec.status
    event.message = spec.message
    event.actor_user_id = spec.actor_user_id
    event.bulk_job_id = spec.bulk_job_id
    return event


def _refresh_record_coverage(record: TLSCertificateInventory) -> None:
    hosts = sorted({str(item) for item in (record.ingress_hosts or []) if item})
    state = db.session.get(TLSCertificateCollectionState, record.cluster_id)
    if state is None or state.ingress_mapping_status != TLS_COLLECTION_COLLECTED:
        record.coverage_state = TLS_COVERAGE_NOT_REPORTED
        record.declared_host_count = len(hosts)
        record.covered_host_count = 0
        record.uncovered_hosts = []
        return
    if not hosts:
        record.coverage_state = TLS_COVERAGE_NONE
        record.declared_host_count = 0
        record.covered_host_count = 0
        record.uncovered_hosts = []
        return
    uncovered = [
        host for host in hosts if matching_certificate_pattern(host, record.dns_names or [], record.common_name) is None
    ]
    covered = len(hosts) - len(uncovered)
    record.coverage_state = (
        TLS_COVERAGE_FULL if not uncovered else TLS_COVERAGE_UNCOVERED if covered == 0 else TLS_COVERAGE_PARTIAL
    )
    record.declared_host_count = len(hosts)
    record.covered_host_count = covered
    record.uncovered_hosts = uncovered


def _apply_parsed_certificate(record: TLSCertificateInventory, parsed: Any) -> None:
    record.common_name = parsed.common_name
    record.issuer = parsed.issuer
    record.serial_number = parsed.serial_number
    record.fingerprint_sha256 = parsed.fingerprint_sha256
    record.dns_names = parsed.dns_names
    record.not_before = parsed.not_before
    record.not_after = parsed.not_after
    record.days_remaining = parsed.days_remaining
    record.status = parsed.status
    record.risk_level = parsed.risk_level
    record.parse_error = None
    _refresh_record_coverage(record)
    record.updated_at = datetime.now(UTC)


def _persist_failure_event(event: TLSCertificateUpdateEvent) -> bool:
    """Persist a provider failure without masking the original operation result."""
    try:
        db.session.rollback()
        db.session.add(event)
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('KAORI could not persist the failed TLS update event.')
        return False


def _coverage_evidence_window() -> timedelta:
    policy = get_or_create_job_policy('governance.tls_certificates.sync')
    return tls_sync_stale_after(policy.interval_minutes)


def _coverage_blocker(record: TLSCertificateInventory, parsed: Any, *, stale_after: timedelta) -> str | None:
    """Require complete, current committed Ingress mapping before PATCH."""
    state = db.session.get(TLSCertificateCollectionState, record.cluster_id)
    if (
        state is None
        or state.secret_collection_status != TLS_COLLECTION_COLLECTED
        or state.ingress_mapping_status != TLS_COLLECTION_COLLECTED
    ):
        return 'Ingress host coverage is Not Reported. Synchronize TLS evidence before rotating this Secret.'
    now = datetime.now(UTC)
    if not (
        tls_sync_evidence_is_current(state.collected_at, stale_after=stale_after, now=now)
        and tls_sync_evidence_is_current(record.collected_at, stale_after=stale_after, now=now)
    ):
        return 'Ingress coverage evidence is stale or unavailable. Synchronize TLS inventory before rotation.'
    uncovered = find_uncovered_hosts(record.ingress_hosts or [], parsed)
    if uncovered:
        return 'Certificate SAN does not cover mapped Ingress hosts: ' + ', '.join(sorted(uncovered))
    return None


def preview_uploaded_pair(files: Any, target_ids: Iterable[int] | None = None) -> dict[str, Any]:
    cert_bytes, key_bytes = read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes,
        key_bytes,
        policy=validity_policy_from_config(current_app.config),
    )
    targets: list[TLSCertificateInventory] = []
    target_previews: list[dict[str, Any]] = []
    requested_ids = [int(item) for item in (target_ids or []) if str(item).isdigit()]

    if requested_ids:
        targets = TLSCertificateInventory.query.filter(TLSCertificateInventory.id.in_(requested_ids)).all()

    if validation.parsed_certificate and targets:
        stale_after = _coverage_evidence_window()
        for target in targets:
            target_view = _target_view(target)
            uncovered_hosts = find_uncovered_hosts(
                target.ingress_hosts or [],
                validation.parsed_certificate,
            )
            blocker = _coverage_blocker(target, validation.parsed_certificate, stale_after=stale_after)
            status = 'blocked' if blocker else 'ready'
            message = blocker or 'Ready to update.'
            target_previews.append(
                {
                    'target': target_view,
                    'status': status,
                    'message': message,
                    'uncovered_hosts': uncovered_hosts,
                    'new_not_after': validation.parsed_certificate.not_after,
                    'new_days_remaining': validation.parsed_certificate.days_remaining,
                    'new_fingerprint_sha256': validation.parsed_certificate.fingerprint_sha256,
                }
            )

    return {
        'validation': validation,
        'targets': target_previews,
        'target_count_requested': len(requested_ids),
    }


def apply_certificate_update(certificate_id: int, files: Any) -> dict[str, Any]:
    record = db.session.get(TLSCertificateInventory, certificate_id)
    if record is None:
        return {
            'status': 'failed',
            'message': 'TLS certificate inventory record was not found.',
            'provider_updated': False,
            'persistence_confirmed': False,
        }

    cert_bytes, key_bytes = read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes,
        key_bytes,
        policy=validity_policy_from_config(current_app.config),
    )
    if not validation.is_valid or validation.parsed_certificate is None:
        return {
            'status': 'failed',
            'message': ' '.join(validation.errors),
            'errors': validation.errors,
            'provider_updated': False,
            'persistence_confirmed': False,
        }

    parsed = validation.parsed_certificate
    coverage_blocker = _coverage_blocker(record, parsed, stale_after=_coverage_evidence_window())
    if coverage_blocker:
        return {
            'status': 'failed',
            'message': coverage_blocker,
            'provider_updated': False,
            'persistence_confirmed': False,
        }
    actor = cast(User, current_user)
    actor_user_id = getattr(actor, 'id', None)
    old_fingerprint = record.fingerprint_sha256
    old_not_after = record.not_after

    try:
        patch_tls_secret(record, cert_bytes, key_bytes)
    except Exception as exc:
        identity_rejected = isinstance(exc, TLSSecretIdentityError)
        if identity_rejected:
            current_app.logger.warning('TLS Secret rotation rejected due to stale target identity.')
        else:
            current_app.logger.exception('Kubernetes TLS Secret mutation failed.')
        safe_message = str(exc) if identity_rejected else 'The Kubernetes TLS Secret could not be updated.'
        failure_event_saved = _persist_failure_event(
            _new_tls_update_event(
                TLSUpdateEventSpec(
                    cluster_id=record.cluster_id,
                    namespace=record.namespace,
                    secret_name=record.secret_name,
                    old_fingerprint_sha256=old_fingerprint,
                    new_fingerprint_sha256=parsed.fingerprint_sha256,
                    old_not_after=old_not_after,
                    new_not_after=parsed.not_after,
                    status='failed',
                    message=safe_message,
                    actor_user_id=actor_user_id,
                )
            )
        )
        return {
            'status': 'failed',
            'message': (
                safe_message
                if identity_rejected
                else (
                    'The Kubernetes TLS Secret could not be updated. Review the cluster connection, '
                    'access permissions, and uploaded certificate pair, then retry.'
                )
            ),
            'provider_updated': False,
            'persistence_confirmed': failure_event_saved,
        }

    _apply_parsed_certificate(record, parsed)
    db.session.add(
        _new_tls_update_event(
            TLSUpdateEventSpec(
                cluster_id=record.cluster_id,
                namespace=record.namespace,
                secret_name=record.secret_name,
                old_fingerprint_sha256=old_fingerprint,
                new_fingerprint_sha256=parsed.fingerprint_sha256,
                old_not_after=old_not_after,
                new_not_after=parsed.not_after,
                status='success',
                message='TLS Secret updated from uploaded certificate and key.',
                actor_user_id=actor_user_id,
            )
        )
    )
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Kubernetes TLS Secret updated, but KAORI posture persistence failed.')
        return {
            'status': 'warning',
            'message': (
                'The TLS Secret was updated in Kubernetes, but KAORI could not confirm its '
                'posture and update-event persistence. Run TLS synchronization before relying '
                'on the displayed certificate posture.'
            ),
            'provider_updated': True,
            'persistence_confirmed': False,
        }

    return {
        'status': 'success',
        'message': 'TLS Secret updated successfully.',
        'provider_updated': True,
        'persistence_confirmed': True,
    }


def _bulk_result_status(results: list[dict[str, Any]]) -> str:
    provider_updated = sum(1 for result in results if result['status'] in {'success', 'warning'})
    warnings = sum(1 for result in results if result['status'] == 'warning')
    failures = sum(1 for result in results if result['status'] == 'failed')
    if provider_updated == 0:
        return 'failed'
    if warnings or failures:
        return 'warning'
    return 'success'


def _bulk_failure_result(message: str, *, errors: list[str] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        'status': 'failed',
        'message': message,
        'results': [],
        'provider_updated_count': 0,
        'persistence_gap_count': 0,
        'failed_count': 0,
    }
    if errors is not None:
        result['errors'] = errors
    return result


def _selected_tls_targets(target_ids: Iterable[int]) -> list[TLSCertificateInventory]:
    ids = [int(item) for item in target_ids if str(item).isdigit()]
    if not ids:
        return []
    return TLSCertificateInventory.query.filter(TLSCertificateInventory.id.in_(ids)).all()


def _summarize_bulk_update_results(results: list[dict[str, Any]], bulk_job_id: str) -> dict[str, Any]:
    """Preserve partial-provider and persistence-gap reporting after TLS writes."""
    provider_updated_count = sum(1 for result in results if result.get('provider_updated') is True)
    persistence_gap_count = sum(
        1
        for result in results
        if result.get('provider_updated') is True and result.get('persistence_confirmed') is False
    )
    failed_count = sum(1 for result in results if result['status'] == 'failed')
    overall_status = _bulk_result_status(results)

    if persistence_gap_count:
        message = (
            f'{provider_updated_count} of {len(results)} selected TLS Secrets were updated in '
            f'Kubernetes; KAORI persistence was not confirmed for '
            f'{persistence_gap_count}. Run TLS synchronization.'
        )
    else:
        message = f'{provider_updated_count} of {len(results)} selected TLS Secrets were updated.' + (
            f' {failed_count} failed.' if failed_count else ''
        )

    return {
        'status': overall_status,
        'message': message,
        'bulk_job_id': bulk_job_id,
        'results': results,
        'provider_updated_count': provider_updated_count,
        'persistence_gap_count': persistence_gap_count,
        'failed_count': failed_count,
    }


def apply_bulk_update(files: Any, target_ids: Iterable[int]) -> dict[str, Any]:
    cert_bytes, key_bytes = read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes,
        key_bytes,
        policy=validity_policy_from_config(current_app.config),
    )
    if not validation.is_valid or validation.parsed_certificate is None:
        return _bulk_failure_result(' '.join(validation.errors), errors=validation.errors)

    # A missing or duplicate ID must never silently narrow a bulk operation.
    requested_ids = [int(item) for item in target_ids if str(item).isdigit()]
    if not requested_ids or len(set(requested_ids)) != len(requested_ids):
        return _bulk_failure_result('Select a unique, valid set of TLS Secrets before applying.')
    targets = _selected_tls_targets(requested_ids)
    if {target.id for target in targets} != set(requested_ids):
        return _bulk_failure_result('The selected TLS Secret target set changed. Refresh selection and validate again.')

    parsed = validation.parsed_certificate
    # Admit the entire selected group before the first provider write.
    stale_after = _coverage_evidence_window()
    coverage_blockers = [
        f'{target.cluster_id}/{target.namespace}/{target.secret_name}: {blocker}'
        for target in targets
        if (blocker := _coverage_blocker(target, parsed, stale_after=stale_after))
    ]
    if coverage_blockers:
        return _bulk_failure_result(
            'TLS coverage admission blocked this bulk operation. No Secret was updated.',
            errors=coverage_blockers,
        )
    # Verify the immutable live identity of the entire group before the
    # first provider PATCH. A race after this point is still stopped by
    # resourceVersion preconditions on dry-run and the actual PATCH.
    prevalidated_versions: dict[int, str] = {}
    for target in targets:
        try:
            prevalidated_versions[int(target.id)] = preflight_tls_secret(target)
        except Exception as exc:
            if isinstance(exc, TLSSecretIdentityError):
                current_app.logger.warning('Bulk TLS rotation preflight rejected a stale target identity.')
                reason = str(exc)
            else:
                current_app.logger.warning('Bulk TLS rotation preflight could not verify a live target.')
                reason = 'Live Secret identity verification failed. Synchronize TLS inventory and retry.'
            return _bulk_failure_result(
                'TLS target identity admission blocked this bulk operation. No Secret was updated.',
                errors=[f'{target.cluster_id}/{target.namespace}/{target.secret_name}: {reason}'],
            )

    bulk_job_id = uuid.uuid4().hex[:16]
    actor = cast(User, current_user)
    actor_user_id = getattr(actor, 'id', None)
    results: list[dict[str, Any]] = []

    for target in targets:
        target_view = _target_view(target)
        old_fingerprint = target.fingerprint_sha256
        old_not_after = target.not_after
        try:
            patch_tls_secret(
                target,
                cert_bytes,
                key_bytes,
                prevalidated_resource_version=prevalidated_versions[int(target.id)],
            )
        except Exception as exc:
            identity_rejected = isinstance(exc, TLSSecretIdentityError)
            if identity_rejected:
                current_app.logger.warning(
                    'Bulk TLS rotation rejected due to stale target identity for %s/%s.',
                    target.namespace,
                    target.secret_name,
                )
            else:
                current_app.logger.exception(
                    'Bulk Kubernetes TLS Secret mutation failed for %s/%s.',
                    target.namespace,
                    target.secret_name,
                )
            safe_message = str(exc) if identity_rejected else 'The Kubernetes TLS Secret could not be updated.'
            db.session.add(
                _new_tls_update_event(
                    TLSUpdateEventSpec(
                        cluster_id=target.cluster_id,
                        namespace=target.namespace,
                        secret_name=target.secret_name,
                        old_fingerprint_sha256=old_fingerprint,
                        new_fingerprint_sha256=parsed.fingerprint_sha256,
                        old_not_after=old_not_after,
                        new_not_after=parsed.not_after,
                        status='failed',
                        message=safe_message,
                        actor_user_id=actor_user_id,
                        bulk_job_id=bulk_job_id,
                    )
                )
            )
            results.append(
                {
                    'target': target_view,
                    'status': 'failed',
                    'message': (
                        safe_message
                        if identity_rejected
                        else 'Kubernetes update failed. Review the cluster connection and access permissions.'
                    ),
                    'provider_updated': False,
                    'persistence_confirmed': True,
                }
            )
            continue

        _apply_parsed_certificate(target, parsed)
        db.session.add(
            _new_tls_update_event(
                TLSUpdateEventSpec(
                    cluster_id=target.cluster_id,
                    namespace=target.namespace,
                    secret_name=target.secret_name,
                    old_fingerprint_sha256=old_fingerprint,
                    new_fingerprint_sha256=parsed.fingerprint_sha256,
                    old_not_after=old_not_after,
                    new_not_after=parsed.not_after,
                    status='success',
                    message='TLS Secret updated by bulk upload.',
                    actor_user_id=actor_user_id,
                    bulk_job_id=bulk_job_id,
                )
            )
        )
        results.append(
            {
                'target': target_view,
                'status': 'success',
                'message': 'Updated.',
                'provider_updated': True,
                'persistence_confirmed': True,
            }
        )

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception('Bulk TLS mutations completed, but KAORI posture persistence failed.')
        for result in results:
            result['persistence_confirmed'] = False
            if result['status'] == 'success':
                result.update(
                    {
                        'status': 'warning',
                        'message': ('Kubernetes updated; KAORI posture persistence was not confirmed.'),
                    }
                )

    return _summarize_bulk_update_results(results, bulk_job_id)

