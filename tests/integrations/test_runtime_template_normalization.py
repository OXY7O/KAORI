from __future__ import annotations

from pathlib import Path

RUNTIME_TEMPLATES = (
    'app/templates/integrations/partials/_runtime_history.html',
    'app/templates/alertmanager/partials/_runtime_panel.html',
    'app/templates/prometheus/partials/_runtime_panel.html',
)


def test_runtime_templates_do_not_format_datetime_or_runtime_keys():
    forbidden = (
        'strftime(',
        '|user_datetime',
        "|replace('_', ' ')|title",
        "|replace('_',' ')|title",
    )
    for filename in RUNTIME_TEMPLATES:
        content = Path(filename).read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in content, (
                f'{filename} still contains presentation formatting: {token}'
            )


def test_prometheus_readiness_datetime_is_presented_in_python():
    content = Path(
        'app/templates/prometheus/partials/_analytics_readiness.html'
    ).read_text(encoding='utf-8')
    assert '|user_datetime' not in content
    assert 'strftime(' not in content
    assert 'config_last_validated_at_display' in content
