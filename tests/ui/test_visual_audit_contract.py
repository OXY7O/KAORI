from __future__ import annotations

import runpy
from pathlib import Path

from PIL import Image, ImageDraw

from app import create_app

ROOT = Path(__file__).resolve().parents[2]
VISUAL_AUDIT = ROOT / 'tests' / 'ui' / 'visual_audit.py'
VISUAL_BASELINES = ROOT / 'tests' / 'ui' / 'baselines' / 'authenticated-visual.json'
PAGE_HERO = ROOT / 'app' / 'templates' / 'components' / 'page_hero.html'
VISUAL_QA_STANDARD = ROOT / 'docs' / 'design' / 'KAORI_VISUAL_QA.md'


def _visual_audit_namespace() -> dict[str, object]:
    assert VISUAL_AUDIT.is_file(), 'shared visual audit authority is required under tests/ui'
    return runpy.run_path(str(VISUAL_AUDIT))


def test_visual_surface_inventory_derives_from_application_route_authority() -> None:
    namespace = _visual_audit_namespace()
    build_inventory = namespace['build_visual_surface_inventory']

    app = create_app('testing')
    inventory = build_inventory(app)  # type: ignore[operator]

    assert inventory
    endpoints = {item.endpoint for item in inventory}
    assert 'welcome.index' in endpoints
    assert all(item.root_label != 'KAORI' for item in inventory)

    source = VISUAL_AUDIT.read_text(encoding='utf-8')
    assert 'app.url_map.iter_rules()' in source
    assert 'build_navigation_breadcrumb' in source
    assert 'CANONICAL_VIEWPORTS =' not in source


def test_visual_surface_inventory_records_determinism_disposition() -> None:
    namespace = _visual_audit_namespace()
    build_inventory = namespace['build_visual_surface_inventory']

    app = create_app('testing')
    inventory = build_inventory(app)  # type: ignore[operator]

    dispositions = {item.disposition for item in inventory}
    assert 'deterministic' in dispositions
    assert 'parameterized' in dispositions
    assert 'runtime-dependent' in dispositions
    assert all(item.rule.startswith('/') for item in inventory)

    by_endpoint = {item.endpoint: item for item in inventory}
    assert by_endpoint['welcome.index'].disposition == 'deterministic'
    assert by_endpoint['settings.general'].disposition == 'deterministic'
    assert by_endpoint['notifications.center'].disposition == 'deterministic'
    assert all(item.disposition == 'parameterized' for item in inventory if '<' in item.rule)


def test_reusable_visual_geometry_assertions_are_one_shared_authority() -> None:
    namespace = _visual_audit_namespace()

    for name in (
        'assert_document_fits_viewport',
        'assert_locator_within_viewport',
        'assert_locator_within_document_width',
        'assert_primary_actions_visible',
        'assert_hero_description_contract',
        'assert_visual_baseline',
    ):
        assert callable(namespace[name]), name

    source = VISUAL_AUDIT.read_text(encoding='utf-8')
    assert 'scrollWidth' in source
    assert 'clientWidth' in source
    assert 'getBoundingClientRect' in source
    assert 'kaori-hero-description' in source
    assert "{'large-desktop', 'laptop', 'compact-laptop', 'tablet'}" in source
    assert 'nowrap' not in source.lower()
    assert 'ellipsis' not in source.lower()


def test_primary_action_geometry_uses_shared_marker_without_below_fold_false_positive() -> None:
    source = VISUAL_AUDIT.read_text(encoding='utf-8')
    hero_source = PAGE_HERO.read_text(encoding='utf-8')

    assert '.kaori-primary-action' in source
    assert '[data-kaori-primary-action]' not in source
    assert 'kaori-primary-action' in hero_source
    assert 'assert_locator_within_document_width' in source


def test_authenticated_visual_baseline_manifest_is_complete_and_reviewable() -> None:
    import json

    baselines = json.loads(VISUAL_BASELINES.read_text(encoding='utf-8'))
    expected_viewports = {
        'large-desktop': (1440, 900),
        'laptop': (1280, 800),
        'compact-laptop': (1024, 768),
        'tablet': (768, 1024),
        'mobile': (390, 844),
        'small-mobile': (360, 800),
    }

    assert len(baselines) == 12
    for theme in ('light', 'dark'):
        for viewport_name, dimensions in expected_viewports.items():
            key = f'welcome-{theme}-{viewport_name}'
            assert key in baselines
            assert baselines[key]['width'] == dimensions[0]
            assert baselines[key]['height'] == dimensions[1]
            assert len(baselines[key]['visual_sha256']) == 64

    source = VISUAL_AUDIT.read_text(encoding='utf-8')
    assert 'DETERMINISTIC_VISUAL_SURFACES' in source
    assert "'settings.general': ('Settings', '/settings/general')" in source
    assert "'notifications.center': ('Notification Center', '/notifications/?view=notifications')" in source
    assert 'KAORI_UPDATE_VISUAL_BASELINES' in source
    assert 'build_visual_thumbnail' in source
    assert 'VISUAL_THUMBNAIL_WIDTH = 128' in source
    assert 'VISUAL_CHANNEL_QUANTUM = 8' in source
    assert 'actual_path.write_bytes(actual_png)' in source
    assert "os.environ.get(VISUAL_BASELINE_UPDATE_ENV) == '1'" in source


def test_visual_thumbnail_normalizes_raster_noise_without_masking_geometry_regression() -> None:
    namespace = _visual_audit_namespace()
    visual_thumbnail_sha256 = namespace['visual_thumbnail_sha256']

    baseline = Image.new('RGB', (320, 200), (248, 247, 252))
    noisy = baseline.copy()
    noisy.putpixel((160, 80), (247, 247, 252))

    assert visual_thumbnail_sha256(baseline) == visual_thumbnail_sha256(noisy)  # type: ignore[operator]

    regressed = baseline.copy()
    draw = ImageDraw.Draw(regressed)
    draw.rectangle((36, 52, 172, 108), fill=(124, 58, 237))

    assert visual_thumbnail_sha256(baseline) != visual_thumbnail_sha256(regressed)  # type: ignore[operator]


def test_visual_audit_report_supports_governed_finding_vocabulary(tmp_path: Path) -> None:
    namespace = _visual_audit_namespace()
    finding_type = namespace['VisualAuditFinding']
    record_finding = namespace['record_visual_audit_finding']

    record_finding(  # type: ignore[operator]
        finding_type(  # type: ignore[operator]
            status='PASS',
            surface='Welcome',
            viewport='laptop',
            theme='light',
            component='Hero',
            invariant='Single-line description',
            evidence='welcome-light-laptop.png',
        ),
        evidence_root=tmp_path,
    )
    record_finding(  # type: ignore[operator]
        finding_type(  # type: ignore[operator]
            status='Needs refinement',
            surface='Welcome',
            viewport='mobile',
            theme='dark',
            component='Workspace Catalog',
            invariant='Visual density review',
            evidence='human-review',
        ),
        evidence_root=tmp_path,
    )
    record_finding(  # type: ignore[operator]
        finding_type(  # type: ignore[operator]
            status='Broken',
            surface='Welcome',
            viewport='tablet',
            theme='dark',
            component='Hero',
            invariant='Visual baseline',
            evidence='welcome-dark-tablet-actual.png',
        ),
        evidence_root=tmp_path,
    )

    json_report = (tmp_path / 'visual-audit-report.json').read_text(encoding='utf-8')
    markdown_report = (tmp_path / 'visual-audit-report.md').read_text(encoding='utf-8')

    assert '"status": "PASS"' in json_report
    assert '"status": "Needs refinement"' in json_report
    assert '"status": "Broken"' in json_report
    assert '# KAORI Visual QA Report' in markdown_report
    assert '| Status | Surface | Viewport | Theme | Component | Invariant | Evidence |' in markdown_report
    assert 'numeric' not in markdown_report.lower()


def test_visual_qa_standard_documents_human_and_machine_authority() -> None:
    standard = VISUAL_QA_STANDARD.read_text(encoding='utf-8')

    for heading in (
        '## Canonical Viewports',
        '## Theme Matrix',
        '## Surface Inventory',
        '## Machine-Enforced Geometry',
        '## Visual Baseline Authority',
        '## Finding Vocabulary',
        '## Human Visual-Review Rubric',
        '## Evidence Report',
        '## CI and Delivery Boundary',
        '## Human UAT Authority',
        '## Baseline Update Procedure',
    ):
        assert heading in standard

    for rubric in (
        'Visual hierarchy',
        'Typography hierarchy',
        'Spacing and rhythm',
        'Alignment',
        'Density',
        'Responsive recomposition',
        'Hero composition',
        'Cards, tables, and forms',
        'Action prominence',
        'Loading, empty, error, blocked, and degraded states',
        'Light/dark parity',
        'Accessibility-visible concerns',
        'Shared-component ownership',
    ):
        assert rubric in standard

    assert 'PASS' in standard
    assert 'Needs refinement' in standard
    assert 'Broken' in standard
    assert 'numeric aesthetic scores' in standard
    assert 'Human UAT remains final authority' in standard
