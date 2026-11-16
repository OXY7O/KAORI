"""Read-only Registry Security posture and empty-state projections.

Provider scan artifacts and committed Registry snapshots remain authoritative.
"""

from __future__ import annotations

from typing import Any


def _security_finding_interpretation(evidence: dict[str, Any]) -> dict[str, str]:
    snapshot = evidence['snapshot']
    scanned_artifacts = evidence['scanned_artifacts']
    artifact_total = evidence['artifact_total']
    finding_total = evidence['finding_total']
    if snapshot['status'] == 'No Artifacts':
        return {
            'title': 'No Artifacts to Scan',
            'description': 'The selected Registry inventory has a committed empty snapshot.',
            'tone': 'info',
            'icon': 'package',
        }
    if snapshot['status'] == 'Not Collected':
        return {
            'title': 'Security Evidence Not Collected',
            'description': 'Run Security Sync before interpreting an empty vulnerability result.',
            'tone': 'unknown',
            'icon': 'clock-alert',
        }
    if snapshot['status'] == 'Refresh Failed':
        return {
            'title': 'Previous Findings Retained',
            'description': 'The latest refresh failed; committed findings still reflect the last successful Security Sync.',
            'tone': 'warning',
            'icon': 'shield-alert',
        }
    if scanned_artifacts == 0:
        return {
            'title': 'No Provider Scan Evidence',
            'description': 'Security Sync found no usable vulnerability scan evidence. KAORI does not trigger provider scans.',
            'tone': 'warning',
            'icon': 'scan-search',
        }
    if scanned_artifacts < artifact_total:
        return {
            'title': 'Partial Scan Coverage',
            'description': f'Findings cover {scanned_artifacts} of {artifact_total} artifacts with usable committed scan evidence.',
            'tone': 'warning',
            'icon': 'scan-search',
        }
    if finding_total == 0:
        return {
            'title': 'No Vulnerabilities Observed',
            'description': 'No findings were observed in the current committed scan evidence for this scope.',
            'tone': 'normal',
            'icon': 'shield-check',
        }
    return {
        'title': 'Committed Evidence',
        'description': (
            'Findings reflect the latest committed provider scan evidence for the selected Registry scope. '
            'Critical and high severity are shown separately in the snapshot and finding rows.'
        ),
        'tone': 'info',
        'icon': 'database',
    }


def _security_finding_empty_state(
    evidence: dict[str, Any],
    *,
    filters_active: bool,
) -> dict[str, str]:
    if filters_active:
        return {
            'label': 'Filtered Security Evidence',
            'title': 'No Findings Match This View',
            'description': 'Adjust the active filters to review other committed vulnerability findings.',
        }
    if evidence['snapshot']['status'] == 'No Artifacts':
        return {
            'label': 'Committed Security',
            'title': 'No Artifacts to Scan',
            'description': 'The selected Registry has a committed empty inventory; no security findings are expected.',
        }
    if evidence['snapshot']['status'] == 'Not Collected':
        return {
            'label': 'Committed Security',
            'title': 'Security Evidence Not Collected',
            'description': 'Run Security Sync to collect provider security evidence for committed artifacts.',
        }
    if evidence['scanned_artifacts'] == 0:
        return {
            'label': 'Committed Security',
            'title': 'No Vulnerability Scan Evidence',
            'description': 'No usable provider scan evidence is committed for this scope. KAORI does not trigger scans.',
        }
    if evidence['finding_total'] == 0:
        return {
            'label': 'Committed Security',
            'title': 'No Vulnerabilities Observed',
            'description': 'No vulnerability findings were observed in the current committed scan evidence.',
        }
    return {
        'label': 'Committed Security',
        'title': 'No Findings Match This Page',
        'description': 'No committed vulnerability finding is available on this page.',
    }


def _security_posture(evidence: dict[str, Any]) -> dict[str, str]:
    if evidence['critical_total']:
        return {'label': 'Critical Findings', 'tone': 'critical'}
    if evidence['high_total']:
        return {'label': 'Review Required', 'tone': 'warning'}
    if evidence['artifact_total'] and evidence['scanned_artifacts'] < evidence['artifact_total']:
        return {'label': 'Coverage Incomplete', 'tone': 'warning'}
    if evidence['artifact_total']:
        return {'label': 'No High-Risk Findings', 'tone': 'normal'}
    return {'label': 'No Evidence', 'tone': 'unknown'}
