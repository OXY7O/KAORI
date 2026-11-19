"""Kubernetes inventory POST actions preserve KAORI's safe relative redirect contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.access.authentication.session import safe_next_url

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ('referrer', 'expected'),
    [
        ('/integrations/kubernetes', '/integrations/kubernetes'),
        ('/inventory/?cluster_id=1', '/inventory/?cluster_id=1'),
        ('https://external.example.invalid/phishing', None),
        ('//external.example.invalid/phishing', None),
        ('/\\external.example.invalid', None),
        ('/inventory/\r\nLocation: https://external.example.invalid', None),
    ],
)
def test_reused_safe_next_url_rejects_cross_origin_referrers(referrer: str, expected: str | None) -> None:
    assert safe_next_url(referrer) == expected


@pytest.mark.parametrize(
    ('source_path', 'guarded_redirects'),
    [
        ('app/kubernetes/inventory/routes.py', 2),
        ('app/kubernetes/cluster/quick_sync.py', 4),
    ],
)
def test_kubernetes_sync_actions_guard_all_referrer_redirects(
    source_path: str, guarded_redirects: int
) -> None:
    source = (ROOT / source_path).read_text(encoding='utf-8')
    assert 'from app.access.authentication.session import safe_next_url' in source
    assert source.count('safe_next_url(request.referrer)') == guarded_redirects
    assert 'redirect(request.referrer or ' not in source
