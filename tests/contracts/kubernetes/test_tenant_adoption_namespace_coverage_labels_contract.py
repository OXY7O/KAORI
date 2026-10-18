from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = 'app/templates/kubernetes/tenant/partials/_tenant_adoption_preflight.html'


def _source() -> str:
    return (ROOT / TEMPLATE_PATH).read_text(encoding='utf-8')


def _labels(values: list[dict], empty_message: str) -> str:
    """Render the actual preflight macro, using KAORI's canonical metadata labels."""
    source = _source()
    start = source.index('{% macro observed_allocation_labels(')
    end = source.index('{%- endmacro %}', start) + len('{%- endmacro %}')
    environment = Environment(
        loader=FileSystemLoader(str(ROOT / 'app/templates')),
        autoescape=True,
    )
    template = environment.from_string(
        '{% import "components/table_label.html" as table_label %}\n' + source[start:end]
    )
    return template.module.observed_allocation_labels(values, empty_message)


def test_namespace_allocation_labels_are_individual_wrapping_metadata_chips() -> None:
    values = [
        {'label': 'CPU Requests', 'value': '2'},
        {'label': 'CPU Limits', 'value': '4'},
        {'label': 'Memory Requests', 'value': '4Gi'},
        {'label': 'Memory Limits', 'value': '8Gi'},
        {'label': 'Pods', 'value': '20'},
        {'label': 'PVCs', 'value': '10'},
        {'label': 'Storage Requests', 'value': '100Gi'},
        {'label': 'Services', 'value': '10'},
        {'label': 'ConfigMaps', 'value': '50'},
        {'label': 'Secrets', 'value': '50'},
    ]
    html = _labels(values, 'No observed quota')

    assert 'flex-wrap' in html
    assert 'aria-label="Observed allocation dimensions"' in html
    assert html.count('kaori-semantic-label') == len(values)
    for value in values:
        assert f'{value["label"]} · {value["value"]}' in html
    assert 'No observed quota' not in html


def test_allocation_labels_escape_untrusted_provider_data_and_preserve_empty_state() -> None:
    unsafe_html = _labels(
        [{'label': '<script>alert(1)</script>', 'value': '2Gi'}],
        'Not available',
    )
    assert '<script>alert(1)</script>' not in unsafe_html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in unsafe_html
    assert '2Gi' in unsafe_html

    empty = _labels([], 'No supported namespaced quota/limit dimensions observed.')
    assert 'No supported namespaced quota/limit dimensions observed.' in empty
    assert 'kaori-semantic-label' not in empty


def test_native_and_capsule_namespace_rows_share_one_renderer_and_semantic_status() -> None:
    source = _source()
    section = source.split('Namespace Coverage', 1)[1].split('Storage &amp; Provider Constraints', 1)[0]

    assert source.count('{% macro observed_allocation_labels(') == 1
    assert section.count('{{ observed_allocation_labels(') == 2
    assert 'allocation.display_values,' in section
    assert "(namespace.get('allocation') or {}).get('display_values', [])" in section
    assert section.count("table_label.status_label('Observed', 'info')") == 2
    assert section.count("table_label.metadata_label('Adopted Baseline', wrap=true)") == 1
    assert section.count("table_label.metadata_label('Observed Baseline' if row.adoption_management_blocker else 'Adopted Baseline', wrap=true)") == 1
    assert 'No supported quota dimensions observed.' in section
    assert 'No supported namespaced quota/limit dimensions observed.' in section
    assert 'Adopted Baseline · Observed</span>' not in section
    assert '{% if not loop.last %} · {% endif %}' not in section


def test_adoption_preflight_discloses_provider_mutations_and_capsule_attach_no_write() -> None:
    source = _source()
    assert 'Capsule Namespace Attachment Preflight' in source
    assert 'Adopted / Provider Mirrored' in source
    assert 'Adopted / Managed' in source
    assert 'No — committed KAORI attachment only' in source
    assert 'Yes — admitted provider allocation cutover and read-back' in source
    assert 'This is not an observation-only action.' in source
    assert 'Provider objects and RBAC remain unchanged.' in source
    assert 'Adoption commits <span class="font-semibold">Adopted / Observed</span> evidence only.' not in source
    assert 'value={{ row.provider_resource_version }}' not in source
    assert 'name="provider_resource_version"' in source


def test_adoption_provider_copy_retains_readback_and_external_constraints() -> None:
    adoption = _source()
    allocation = (ROOT / 'app/kubernetes/tenant/allocation_cutover.py').read_text(encoding='utf-8')
    assert 'Kubernetes/Capsule remains authoritative.' in adoption
    assert 'by provider read-back and preserves external constraints.' in adoption
    assert 'KAORI Managed Namespace allocation verified by Native Kubernetes read-back.' in allocation
    assert 'Adoption origin retained in evidence.' in allocation


def test_capsule_preflight_blocks_unadmitted_quota_without_offering_submit() -> None:
    source = _source()
    # A Capsule Tenant with observed Native namespaced quota must not be
    # presented as eligible for provider-authoritative managed cutover.
    assert 'data-capsule-adoption-authority-blocked' in source
    assert 'Managed Adoption Blocked' in source
    assert 'row.adoption_management_blocker' in source
    assert 'row.provider_key == \'capsule\' and row.adoption_management_blocker' in source
    assert 'aria-label="Managed adoption blocked by unadmitted Capsule quota authority"' in source
    assert 'disabled' in source
    assert 'Adoption Blocked' in source
    assert 'Control Unavailable.' in source
    # A blocked preflight must never advertise future write/read-back as an
    # adoption result, despite retaining those descriptions for eligible paths.
    for blocked_copy in (
        'Managed adoption unavailable.',
        'No KAORI governance record will be committed while managed adoption is blocked.',
        'Not Adopted · Control Unavailable',
        'Not Eligible · Control Unavailable',
        'No adoption or quota transfer can be committed from this preflight.',
        'No adoption committed',
        'Not permitted — managed adoption blocked',
        'No Tenant-wide quota observed; namespaced allocation remains provider-owned',
    ):
        assert blocked_copy in source
    assert "Observed Baseline' if row.adoption_management_blocker else 'Adopted Baseline'" in source
    assert "if row.provider_key == 'capsule' and row.adoption_management_blocker" in source
    assert source.count('type="submit"') == 1
    assert 'aria-disabled="true"' in source
    assert 'Attach Capsule Namespace' in source
    assert 'Adopt & Manage' in source
    # The route/form remains intact for eligible managed adoption or mirror-only
    # namespace attachment; no additional write endpoint is created.
    assert source.count('type="submit"') == 1
    assert 'tenant.adopt_discovered_tenant_route' in source
    assert 'name="csrf_token"' in source
