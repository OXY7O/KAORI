"""Kubernetes Admin namespace filters expose programmatic accessible names."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_secret_reveal_namespace_filters_have_matching_label_and_control_ids() -> None:
    source = (
        ROOT / 'app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_section.html'
    ).read_text(encoding='utf-8')
    assert 'for="secret-reveal-namespace-search"' in source
    assert 'id="secret-reveal-namespace-search"' in source
    assert 'name="namespace_q"' in source
    assert 'for="secret-reveal-namespace-policy-filter"' in source
    assert 'id="secret-reveal-namespace-policy-filter"' in source
    assert 'name="namespace_policy"' in source
    assert 'hx-target="#secret-reveal-namespace-table-content"' in source
