from __future__ import annotations

_GOVERNANCE_SIGNAL_LABELS = {
    'Without ResourceQuota': 'ResourceQuota Gap',
    'With Incomplete Requests': 'Requests Gap',
    'Need Memory Limit Review': 'Memory Limit Review',
    'BestEffort Workloads': 'BestEffort Review',
    'Incomplete Metrics Coverage': 'Metrics Coverage',
    'Need Right-Sizing Review': 'Right-Sizing Review',
}


def compact_governance_signal(title: str) -> str:
    for marker, label in _GOVERNANCE_SIGNAL_LABELS.items():
        if marker in title:
            return label
    return title
