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
        '{% import "components/table_label.html" as table_label %}\n'
        + source[start:end]
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
        assert f"{value['label']} · {value['value']}" in html
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
    assert "allocation.display_values," in section
    assert "(namespace.get('allocation') or {}).get('display_values', [])" in section
    assert section.count("table_label.status_label('Observed', 'info')") == 2
    assert section.count("table_label.metadata_label('Adopted Baseline', wrap=true)") == 2
    assert 'No supported quota dimensions observed.' in section
    assert 'No supported namespaced quota/limit dimensions observed.' in section
    assert 'Adopted Baseline · Observed</span>' not in section
    assert '{% if not loop.last %} · {% endif %}' not in section
