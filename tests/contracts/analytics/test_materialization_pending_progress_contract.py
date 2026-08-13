from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_ROOT = Path('app/templates')


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_ROOT)),
        undefined=StrictUndefined,
        autoescape=True,
    )


def test_pending_partial_renders_without_optional_progress_values() -> None:
    template = _environment().get_template('analytics/materialization/_pending.html')

    rendered = template.render(
        materialization_status_url='/analytics/materialization/status',
        materialization_return_url='/analytics/alerts',
    )

    assert 'Analytics Data Preparation' in rendered
    assert 'Analytics data preparation in progress' in rendered
    assert 'aria-valuenow=' not in rendered


def test_pending_partial_renders_numeric_worker_progress() -> None:
    template = _environment().get_template('analytics/materialization/_pending.html')

    rendered = template.render(
        materialization_status_url='/analytics/materialization/status',
        materialization_return_url='/analytics/alerts',
        materialization_error=None,
        materialization_progress_message='Collecting alert signals',
        materialization_progress_percent=42,
    )

    assert 'aria-valuenow="42"' in rendered
    assert 'kaori-progress-fill' in rendered
    assert 'data-progress="42"' in rendered
    assert 'style="width: 42%"' in rendered
    assert 'Collecting alert signals' in rendered
    assert '>42%</span>' in rendered


def test_pending_context_contract_always_defines_progress_fields() -> None:
    source = Path('app/analytics/materialization/presentation.py').read_text()

    assert "'materialization_progress_message': progress_message" in source
    assert "'materialization_progress_percent': progress_percent" in source
    assert "'materialization_error': materialization_error" in source


def test_progress_bar_macro_is_safe_for_missing_optional_value() -> None:
    source = Path('app/templates/components/progress_bar.html').read_text()

    assert 'value | default(0, true) | int' in source
    assert 'aria-valuenow="{{ safe_value }}"' in source
