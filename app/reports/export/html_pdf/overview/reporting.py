from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .common import integer, mapping, sequence, text, tone


def report_activity(reports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = {'Ready': 0, 'Generating': 0, 'Failed': 0, 'Other': 0}
    tones = {'Ready': 'normal', 'Generating': 'info', 'Failed': 'critical', 'Other': 'neutral'}
    for report in reports:
        label = text(report.get('status'), 'Other').lower()
        bucket = _activity_bucket(label)
        counts[bucket] += 1
    maximum = max(counts.values(), default=0) or 1
    return [
        {
            'label': label,
            'value': value,
            'percent': value / maximum * 100.0,
            'tone': tones[label],
        }
        for label, value in counts.items()
        if value or label in {'Ready', 'Generating', 'Failed'}
    ]


def _activity_bucket(label: str) -> str:
    if 'ready' in label or 'complete' in label or 'available' in label:
        return 'Ready'
    if 'generat' in label or 'running' in label or 'pending' in label:
        return 'Generating'
    if 'fail' in label or 'error' in label:
        return 'Failed'
    return 'Other'


def title_like(value: str) -> str:
    rendered = text(value)
    if not rendered:
        return rendered
    specials = {'s3': 'S3', 'cpu': 'CPU', 'p95': 'P95', 'api': 'API', 'utc': 'UTC'}
    words = []
    for word in rendered.split():
        key = word.lower()
        words.append(specials.get(key, word if any(ch.isupper() for ch in word[1:]) else word.capitalize()))
    return ' '.join(words)


def reporting(reporting_summary: Mapping[str, Any]) -> dict[str, Any]:
    counts = mapping(reporting_summary.get('counts'))
    recent = sequence(reporting_summary.get('recent_reports'))
    schedules = sequence(reporting_summary.get('schedules'))
    storage = mapping(reporting_summary.get('storage'))
    generated = integer(counts.get('generated_this_month') or counts.get('total'))
    normalized_recent = [normalize_recent_report(item) for item in recent[:6]]
    failed = integer(counts.get('failed'))
    return {
        'metrics': _report_metrics(counts, generated, failed),
        'recent_reports': normalized_recent,
        'activity': report_activity(normalized_recent),
        'schedules': [normalize_schedule(item) for item in schedules[:6]],
        'storage': _storage_summary(storage),
        'notes': sequence(reporting_summary.get('notes'))
        or [
            'Generated report records use the canonical KAORI WeasyPrint pipeline.',
            'Scheduled definitions and generated artifacts remain separate governed records.',
        ],
        'takeaway': (
            'Reporting operations are available. Review failed records and storage posture before expanding schedule volume.'
            if failed
            else 'Reporting operations are healthy within the available generation and storage evidence.'
        ),
    }


def _report_metrics(counts: Mapping[str, Any], generated: int, failed: int) -> list[dict[str, Any]]:
    return [
        {
            'label': 'Reports Generated',
            'value': str(generated),
            'note': 'Current reporting period',
            'tone': 'info',
        },
        {
            'label': 'Scheduled Reports',
            'value': str(integer(counts.get('active_schedules'))),
            'note': 'Active schedules',
            'tone': 'normal',
        },
        {
            'label': 'Ready Reports',
            'value': str(integer(counts.get('ready'))),
            'note': 'Available for download',
            'tone': 'info',
        },
        {
            'label': 'Failed Reports',
            'value': str(failed),
            'note': 'Requires review',
            'tone': 'critical' if failed else 'normal',
        },
    ]


def _storage_summary(storage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'backend': title_like(text(storage.get('backend'), 'Not Available')),
        'status': title_like(text(storage.get('status'), 'Not Available')),
        'tone': tone(storage.get('tone')),
        'description': text(storage.get('description'), 'Storage utilization detail is not available.'),
    }


def normalize_recent_report(item: Any) -> dict[str, Any]:
    row = mapping(item)
    return {
        'name': text(row.get('name'), 'Unnamed Report'),
        'type': text(row.get('report_type_label') or row.get('type'), 'Report'),
        'generated_at': text(
            row.get('created_at_display') or row.get('generated_at') or row.get('created_at'),
            'Not Available',
        ),
        'size': text(row.get('file_size_display') or row.get('size'), 'Not Available'),
        'status': text(row.get('status_label') or row.get('status'), 'Unknown'),
        'tone': tone(row.get('status_tone') or row.get('status')),
    }


def normalize_schedule(item: Any) -> dict[str, Any]:
    row = mapping(item)
    return {
        'name': text(row.get('name'), 'Unnamed Schedule'),
        'frequency': text(row.get('cadence_label') or row.get('cadence'), 'Not Available'),
        'next_run': text(row.get('next_run_at_display') or row.get('next_run_at'), 'Not Available'),
        'status': text(
            row.get('status_label') or ('Active' if row.get('is_enabled') else 'Disabled'),
            'Unknown',
        ),
        'tone': 'normal' if row.get('is_enabled') else 'neutral',
    }
