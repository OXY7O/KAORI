from pathlib import Path

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    select_autoescape,
)


ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = ROOT / 'app' / 'templates'


def test_shared_operation_action_bar_renders_call_block_directly() -> None:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        undefined=StrictUndefined,
        autoescape=select_autoescape(['html', 'xml']),
    )
    template = environment.from_string(
        """
        {% import "components/kubernetes_operation_ui.html" as operation_ui %}
        {% call operation_ui.action_bar(
            'scan-search',
            'Validate Before Creation',
            'Validate the manifest before applying it.'
        ) %}
            <button type="button">Validate</button>
            <button type="submit">Create</button>
        {% endcall %}
        """
    )

    rendered = template.render()

    assert 'Validate Before Creation' in rendered
    assert '<button type="button">Validate</button>' in rendered
    assert '<button type="submit">Create</button>' in rendered


def test_operation_templates_do_not_use_domain_component_wrappers() -> None:
    templates = ROOT / 'app' / 'templates' / 'kubernetes_operations'
    wrapper_paths = (
        templates / 'configmaps' / '_components.html',
        templates / 'secrets' / '_components.html',
    )

    assert all(not path.exists() for path in wrapper_paths)

    for template in templates.rglob('*.html'):
        source = template.read_text()
        assert 'kubernetes_operations/configmaps/_components.html' not in source
        assert 'kubernetes_operations/secrets/_components.html' not in source
