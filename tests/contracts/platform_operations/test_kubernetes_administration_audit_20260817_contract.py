import re
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def has_jinja_assignment(source: str, variable: str, value: str) -> bool:
    pattern = r'{%\s*set\s+' + re.escape(variable) + r"\s*=\s*([\"'])" + re.escape(value) + r'\1\s*%}'
    return re.search(pattern, source) is not None


def test_kubernetes_administration_posture_is_factual_not_hardcoded_available() -> None:
    presentation = read('app/platform_operations/kubernetes/presentation.py')
    page = read('app/templates/platform_operations/kubernetes/index.html')
    overview = read('app/templates/platform_operations/kubernetes/_overview_workspace.html')

    assert 'def _administration_posture(' in presentation
    for label in (
        'Setup Required',
        'Global Gate Disabled',
        'Readiness Review',
        'Partial Readiness',
        'Policy Required',
        'Verification Required',
    ):
        assert label in presentation
    assert "'administration_status_label': status_label" in presentation
    assert "'administration_status_tone': status_tone" in presentation
    assert "'administration_status_detail': status_detail" in presentation

    assert 'Control Status: Protected Secret Reveal Available' not in page
    assert 'Available Controls' not in page
    assert 'Managed Controls' in overview
    assert 'administration_status_label' in page
    assert 'administration_status_tone' in page
    assert 'administration_status_detail' in presentation
    assert 'control.status_detail' in read(
        'app/templates/platform_operations/kubernetes/_administration_control_rows.html'
    )
    assert "table_label.status_label('Available', 'normal')" not in overview
    assert "table_label.status_label('1 Available Control', 'info')" not in overview
    assert 'table_label.status_indicator_label(administration_status_label, administration_status_tone)' in overview
    assert 'Counts represent committed KAORI configuration.' in overview


def test_secret_reveal_readiness_fails_closed_when_canonical_connection_is_missing() -> None:
    policy = read('app/kubernetes/operations/secrets/reveal_policy.py')

    readiness = policy.split('def cluster_reveal_readiness_evidence(', 1)[1].split('def cluster_reveal_readiness(', 1)[
        0
    ]
    assert 'try:' in readiness
    assert 'credential_configured = bool(kubeconfig_for_cluster(cluster))' in readiness
    assert 'except (RuntimeError, ValueError):' in readiness
    assert 'credential_configured = False' in readiness


def test_kubernetes_administration_no_cluster_and_namespace_states_are_canonical() -> None:
    cluster = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    namespace = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')

    assert has_jinja_assignment(cluster, 'empty_state_title', 'No Kubernetes Cluster Registered')
    assert has_jinja_assignment(cluster, 'empty_state_permission', 'clusters.manage')
    assert 'empty_state_show_admin_required = true' in cluster
    assert 'p-8 text-center' not in cluster

    assert has_jinja_assignment(namespace, 'empty_state_title', 'No Namespace Matches the Current Filters')
    assert has_jinja_assignment(namespace, 'blocked_state_title', 'Live Namespace Source Unavailable')
    assert has_jinja_assignment(namespace, 'empty_state_title', 'No Live Namespace Available')


def test_kubernetes_administration_summaries_use_title_adjacent_shared_guides() -> None:
    overview = read('app/templates/platform_operations/kubernetes/_overview_workspace.html')
    reveal = read('app/templates/platform_operations/kubernetes/_secret_reveal_workspace.html')
    card = read('app/templates/components/operational_section_card.html')
    guide = read('app/templates/components/info_tip.html')

    for source, guide_id, badge in (
        (
            overview,
            'kubernetes-administration-coverage-guide',
            'table_label.status_indicator_label(administration_status_label, administration_status_tone)',
        ),
        (
            reveal,
            'kubernetes-secret-reveal-configuration-guide',
            "table_label.status_indicator_label('Global Gate Enabled' if global_reveal_enabled",
        ),
    ):
        Environment().parse(source)
        assert '{% import "components/info_tip.html" as info_tip %}' in source
        assert source.count("variant='guide'") == 1
        badge_position = source.index(badge)
        trigger_position = source.index(f"'{guide_id}'")
        assert badge_position < trigger_position < source.index('{% endset %}', trigger_position)
        assert "placement='right'" in source
        assert 'header_badge=' in source

    assert 'flex flex-wrap items-center gap-2' in card
    assert '{% if header_badge %}{{ header_badge }}{% endif %}' in card
    assert 'data-kaori-info-tip-variant=' in guide
    assert 'data-kaori-info-tip-trigger' in guide
    assert "'Open guide: '" in guide
    assert 'Counts represent committed KAORI configuration.' in overview
    assert 'Configured prerequisites and policies do not prove live access.' in reveal
    assert 'Kubernetes RBAC' in reveal
    assert "info_tip.render('kubernetes-administration-coverage-guide'" in overview
    assert "info_tip.render('kubernetes-secret-reveal-configuration-guide'" in reveal


def test_kubernetes_secret_boundary_copy_fits_compact_desktop_columns() -> None:
    boundary = read('app/templates/platform_operations/kubernetes/secret_reveal/_cluster_workspace.html')
    Environment().parse(boundary)

    assert "'Namespace Scope', 'Use namespace Role and RoleBinding.'" in boundary
    assert "'Credential Scope', 'Review kubeconfig scope as roles change.'" in boundary
    assert 'Prefer namespace Role and RoleBinding where practical.' not in boundary
    assert 'Review kubeconfig access when responsibilities change.' not in boundary
    assert 'sm:grid-cols-2 xl:grid-cols-4' in boundary
    assert 'text-xs leading-5 text-content-secondary' in boundary
    assert 'Kubernetes RBAC remains the final authorization boundary.' in boundary
    assert 'Configured readiness does not establish live Secret access.' in boundary
    assert 'whitespace-nowrap' not in boundary.split('Namespace Scope', 1)[1].split('{% endfor %}', 1)[0]
