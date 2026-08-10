from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from flask import current_app
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.governance.tls_certificates.certificate import (
    find_uncovered_hosts,
    matching_certificate_pattern,
    validate_certificate_pair,
    validity_policy_from_config,
)
from app.governance.tls_certificates.constants import (
    TLS_COLLECTION_COLLECTED,
    TLS_COVERAGE_FULL,
    TLS_COVERAGE_NONE,
    TLS_COVERAGE_NOT_REPORTED,
    TLS_COVERAGE_PARTIAL,
    TLS_COVERAGE_UNCOVERED,
)
from app.governance.tls_certificates.mutation import patch_tls_secret, read_uploaded_pair
from app.models import (
    TLSCertificateCollectionState,
    TLSCertificateInventory,
    TLSCertificateUpdateEvent,
    User,
)


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


def preview_uploaded_pair(files: Any, target_ids: Iterable[int] | None = None) -> dict[str, Any]:
    cert_bytes, key_bytes = read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes,
        key_bytes,
        policy=validity_policy_from_config(current_app.config),
    )
    targets: list[TLSCertificateInventory] = []
    target_previews: list[dict[str, Any]] = []

    if target_ids:
        ids = [int(item) for item in target_ids if str(item).isdigit()]
        targets = TLSCertificateInventory.query.filter(TLSCertificateInventory.id.in_(ids)).all() if ids else []

    if validation.parsed_certificate and targets:
        for target in targets:
            target_view = _target_view(target)
            uncovered_hosts = find_uncovered_hosts(
                target.ingress_hosts or [],
                validation.parsed_certificate,
            )
            status = 'warning' if uncovered_hosts else 'ready'
            message = (
                'Certificate SAN does not cover all currently mapped Ingress hosts.'
                if uncovered_hosts
                else 'Ready to update.'
            )
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
    actor = cast(User, current_user)
    actor_user_id = getattr(actor, 'id', None)
    old_fingerprint = record.fingerprint_sha256
    old_not_after = record.not_after

    try:
        patch_tls_secret(record, cert_bytes, key_bytes)
    except Exception:
        current_app.logger.exception('Kubernetes TLS Secret mutation failed.')
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
                    message='The Kubernetes TLS Secret could not be updated.',
                    actor_user_id=actor_user_id,
                )
            )
        )
        return {
            'status': 'failed',
            'message': (
                'The Kubernetes TLS Secret could not be updated. Review the cluster connection, '
                'access permissions, and uploaded certificate pair, then retry.'
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


def apply_bulk_update(files: Any, target_ids: Iterable[int]) -> dict[str, Any]:
    cert_bytes, key_bytes = read_uploaded_pair(files)
    validation = validate_certificate_pair(
        cert_bytes,
        key_bytes,
        policy=validity_policy_from_config(current_app.config),
    )
    if not validation.is_valid or validation.parsed_certificate is None:
        return _bulk_failure_result(' '.join(validation.errors), errors=validation.errors)

    targets = _selected_tls_targets(target_ids)
    if not targets:
        return _bulk_failure_result('No TLS Secrets were selected.')

    parsed = validation.parsed_certificate
    bulk_job_id = uuid.uuid4().hex[:16]
    actor = cast(User, current_user)
    actor_user_id = getattr(actor, 'id', None)
    results: list[dict[str, Any]] = []

    for target in targets:
        target_view = _target_view(target)
        old_fingerprint = target.fingerprint_sha256
        old_not_after = target.not_after
        try:
            patch_tls_secret(target, cert_bytes, key_bytes)
        except Exception:
            current_app.logger.exception(
                'Bulk Kubernetes TLS Secret mutation failed for %s/%s.',
                target.namespace,
                target.secret_name,
            )
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
                        message='The Kubernetes TLS Secret could not be updated.',
                        actor_user_id=actor_user_id,
                        bulk_job_id=bulk_job_id,
                    )
                )
            )
            results.append(
                {
                    'target': target_view,
                    'status': 'failed',
                    'message': ('Kubernetes update failed. Review the cluster connection and access permissions.'),
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
