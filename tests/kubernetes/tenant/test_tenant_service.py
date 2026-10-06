import pytest

from app.kubernetes.tenant.service import normalize_tenant_slug


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('Payments', 'payments'),
        ('Payments Platform', 'payments-platform'),
        ('payments_core', 'payments-core'),
    ],
)
def test_normalize_tenant_slug(source: str, expected: str) -> None:
    assert normalize_tenant_slug(source) == expected


def test_normalize_tenant_slug_rejects_empty_or_overlong_values() -> None:
    with pytest.raises(ValueError):
        normalize_tenant_slug('---')
    with pytest.raises(ValueError):
        normalize_tenant_slug('a' * 64)
