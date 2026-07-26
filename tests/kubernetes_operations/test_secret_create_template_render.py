from __future__ import annotations

from pathlib import Path

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, StrictUndefined, select_autoescape


TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / 'app' / 'templates'


def _template_environment() -> Environment:
    """Render the workflow body without requiring the full Flask layout context."""
    environment = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(
                    {
                        'layouts/app.html': (
                            '<!doctype html><html><body>'
                            '{% block dashboard_content %}{% endblock dashboard_content %}'
                            '</body></html>'
                        )
                    }
                ),
                FileSystemLoader(TEMPLATE_ROOT),
            ]
        ),
        undefined=StrictUndefined,
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.globals['url_for'] = lambda endpoint, **values: f'/{endpoint}'
    return environment


def test_create_secret_template_renders_shared_status_labels() -> None:
    rendered = _template_environment().get_template(
        'kubernetes_operations/secrets/create.html'
    ).render(
        submitted={},
        opaque_entries=[{'key': '', 'value': '', 'visible': False}],
        clusters=[],
        namespace_options={},
        namespace_selection_error=None,
        secret_types={},
        operation_feedback=None,
    )

    assert 'Disabled' in rendered
    assert 'Dry-Run Required' in rendered
    assert rendered.count('kaori-semantic-label') >= 2
