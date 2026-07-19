from pathlib import Path


STYLES = Path('frontend/styles.css')
TABLE_LABEL = Path('app/templates/components/table_label.html')
PAGE_HERO = Path('app/templates/components/page_hero.html')
STATUS_BADGE = Path('app/templates/integrations/partials/_status_badge.html')

ALERTMANAGER_TEMPLATES = (
    Path('app/templates/integrations/alertmanager.html'),
    Path('app/templates/alertmanager/instance_form.html'),
    Path('app/templates/alertmanager/instance_detail.html'),
)
PROMETHEUS_TEMPLATES = (
    Path('app/templates/integrations/prometheus.html'),
    Path('app/templates/prometheus/instance_form.html'),
    Path('app/templates/prometheus/instance_detail.html'),
    Path('app/templates/prometheus/instances.html'),
    Path('app/templates/prometheus/config.html'),
)


def test_alertmanager_and_prometheus_use_final_semantic_palette() -> None:
    source = STYLES.read_text(encoding='utf-8').lower()
    expected = (
        '--kaori-brand-primary: #7c3aed;',
        '--kaori-brand-primary-hover: #6d28d9;',
        '--kaori-brand-soft: #f5f3ff;',
        '--kaori-brand-border: #c4b5fd;',
        '--kaori-status-info: #2563eb;',
        '--kaori-status-info-text: #1d4ed8;',
        '--kaori-status-info-soft: #eff6ff;',
        '--kaori-status-info-border: #bfdbfe;',
        '--kaori-status-normal: #059669;',
        '--kaori-status-normal-text: #047857;',
        '--kaori-status-normal-soft: #ecfdf5;',
        '--kaori-status-normal-border: #a7f3d0;',
        '--kaori-status-warning: #d97706;',
        '--kaori-status-warning-text: #b45309;',
        '--kaori-status-warning-soft: #fffbeb;',
        '--kaori-status-warning-border: #fde68a;',
        '--kaori-status-critical: #dc2626;',
        '--kaori-status-critical-text: #b91c1c;',
        '--kaori-status-critical-soft: #fef2f2;',
        '--kaori-status-critical-border: #fecaca;',
        '--kaori-status-unknown: #64748b;',
        '--kaori-status-unknown-text: #475569;',
        '--kaori-status-unknown-soft: #f8fafc;',
        '--kaori-status-unknown-border: #cbd5e1;',
    )
    missing = [item for item in expected if item not in source]
    assert not missing, f'Final KAORI semantic colors are missing: {missing}'


def test_integration_labels_are_borderless_inside_rollout_scope() -> None:
    styles = STYLES.read_text(encoding='utf-8')
    table_label = TABLE_LABEL.read_text(encoding='utf-8')
    hero = PAGE_HERO.read_text(encoding='utf-8')
    badge = STATUS_BADGE.read_text(encoding='utf-8')

    assert '.kaori-integration-semantic .kaori-semantic-label,' in styles
    assert '.kaori-integration-semantic .kaori-context-label {' in styles
    assert 'border-width: 0;' in styles
    assert 'kaori-semantic-label' in table_label
    assert 'kaori-semantic-label' in badge
    assert 'text-status-normal' in badge and 'text-status-normal-text' in badge
    assert 'text-kaori-primary' in table_label and 'text-kaori-primary-dark' in table_label
    assert hero.count('kaori-context-label') >= 2


def test_integration_pages_opt_into_scoped_semantic_contract() -> None:
    for template in ALERTMANAGER_TEMPLATES + PROMETHEUS_TEMPLATES:
        source = template.read_text(encoding='utf-8')
        assert 'kaori-integration-semantic' in source, f'{template} is outside semantic rollout scope'


def test_active_alertmanager_and_prometheus_templates_have_no_raw_status_colors_or_monospace() -> None:
    roots = (
        Path('app/templates/alertmanager'),
        Path('app/templates/integrations/alertmanager.html'),
        Path('app/templates/integrations/alertmanager'),
        Path('app/templates/prometheus'),
        Path('app/templates/integrations/prometheus.html'),
        Path('app/templates/integrations/prometheus'),
    )
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.exists():
            files.extend(root.rglob('*.html'))

    forbidden = (
        'font-mono',
        'text-emerald-',
        'bg-emerald-',
        'border-emerald-',
        'text-red-',
        'bg-red-',
        'border-red-',
        'text-amber-',
        'bg-amber-',
        'border-amber-',
        'text-blue-',
        'bg-blue-',
        'border-blue-',
        'text-slate-',
        'bg-slate-',
        'border-slate-',
    )
    violations: list[str] = []
    for template in files:
        source = template.read_text(encoding='utf-8')
        for token in forbidden:
            if token in source:
                violations.append(f'{template}:{token}')
    assert not violations, f'Active integration templates contain raw color/font utilities: {violations}'
