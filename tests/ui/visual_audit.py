from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from flask import Flask
from PIL import Image
from playwright.sync_api import Locator, Page

from app.common.navigation import build_navigation_breadcrumb

VisualDisposition = Literal['deterministic', 'parameterized', 'runtime-dependent']
VisualFindingStatus = Literal['PASS', 'Needs refinement', 'Broken']

VISUAL_BASELINE_MANIFEST = Path('tests/ui/baselines/authenticated-visual.json')
VISUAL_EVIDENCE_ROOT = Path('tmp/ci-artifacts/test-output/ui-browser')
VISUAL_BASELINE_UPDATE_ENV = 'KAORI_UPDATE_VISUAL_BASELINES'
VISUAL_THUMBNAIL_WIDTH = 128
VISUAL_CHANNEL_QUANTUM = 8

DETERMINISTIC_VISUAL_SURFACES: dict[str, tuple[str, str]] = {
    'welcome.index': ('Welcome', '/welcome'),
    'settings.general': ('Settings', '/settings/general'),
    'notifications.center': ('Notification Center', '/notifications/?view=notifications'),
}


@dataclass(frozen=True)
class VisualSurface:
    endpoint: str
    rule: str
    root_label: str
    disposition: VisualDisposition


@dataclass(frozen=True)
class VisualAuditFinding:
    status: VisualFindingStatus
    surface: str
    viewport: str
    theme: str
    component: str
    invariant: str
    evidence: str


def build_visual_surface_inventory(app: Flask) -> tuple[VisualSurface, ...]:
    surfaces: list[VisualSurface] = []

    for rule in app.url_map.iter_rules():
        if 'GET' not in rule.methods:
            continue
        if rule.endpoint == 'static' or rule.endpoint.endswith('.static'):
            continue

        breadcrumb = build_navigation_breadcrumb(rule.endpoint, rule.rule)
        if not breadcrumb:
            continue

        root_label = str(breadcrumb[0].get('label') or 'KAORI')
        if root_label == 'KAORI':
            continue

        if rule.arguments:
            disposition: VisualDisposition = 'parameterized'
        elif rule.endpoint in DETERMINISTIC_VISUAL_SURFACES:
            disposition = 'deterministic'
        else:
            disposition = 'runtime-dependent'
        surfaces.append(
            VisualSurface(
                endpoint=rule.endpoint,
                rule=rule.rule,
                root_label=root_label,
                disposition=disposition,
            )
        )

    return tuple(sorted(surfaces, key=lambda item: (item.root_label, item.endpoint, item.rule)))


def assert_document_fits_viewport(page: Page) -> None:
    dimensions = page.evaluate(
        '() => ({ scrollWidth: document.documentElement.scrollWidth, '
        'clientWidth: document.documentElement.clientWidth })'
    )
    assert dimensions['scrollWidth'] <= dimensions['clientWidth'] + 1


def assert_locator_within_viewport(page: Page, locator: Locator, *, label: str) -> None:
    assert locator.is_visible(), f'{label} must be visible'
    box = locator.bounding_box()
    viewport = page.viewport_size

    assert box is not None, f'{label} must have rendered geometry'
    assert viewport is not None, f'{label} requires an explicit browser viewport'
    assert box['x'] >= -1, f'{label} escapes the left viewport edge'
    assert box['y'] >= -1, f'{label} escapes the top viewport edge'
    assert box['x'] + box['width'] <= viewport['width'] + 1, f'{label} escapes the right viewport edge'
    assert box['y'] + box['height'] <= viewport['height'] + 1, f'{label} escapes the bottom viewport edge'


def assert_locator_within_document_width(page: Page, locator: Locator, *, label: str) -> None:
    assert locator.is_visible(), f'{label} must be visible'
    box = locator.bounding_box()
    dimensions = page.evaluate('() => ({ clientWidth: document.documentElement.clientWidth })')

    assert box is not None, f'{label} must have rendered geometry'
    assert box['width'] > 0 and box['height'] > 0, f'{label} must have non-zero rendered geometry'
    assert box['x'] >= -1, f'{label} escapes the left document edge'
    assert box['x'] + box['width'] <= dimensions['clientWidth'] + 1, f'{label} escapes the right document edge'


def assert_primary_actions_visible(page: Page, selector: str = '.kaori-primary-action') -> None:
    actions = page.locator(selector)
    for index in range(actions.count()):
        action = actions.nth(index)
        if not action.is_visible():
            continue

        label = f'primary action #{index + 1}'
        position = action.evaluate('element => window.getComputedStyle(element).position')
        if position in {'fixed', 'sticky'}:
            assert_locator_within_viewport(page, action, label=label)
            continue
        assert_locator_within_document_width(page, action, label=label)


def assert_hero_description_contract(page: Page, viewport_name: str) -> None:
    descriptions = page.locator('.kaori-hero-description')

    for index in range(descriptions.count()):
        description = descriptions.nth(index)
        if not description.is_visible():
            continue

        metrics = description.evaluate(
            """element => {
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return {
                    clientWidth: element.clientWidth,
                    scrollWidth: element.scrollWidth,
                    height: rect.height,
                    lineHeight: Number.parseFloat(style.lineHeight),
                };
            }"""
        )
        assert metrics['scrollWidth'] <= metrics['clientWidth'] + 1

        if viewport_name in {'large-desktop', 'laptop', 'compact-laptop', 'tablet'}:
            assert metrics['height'] <= metrics['lineHeight'] + 1


def build_visual_thumbnail(image: Image.Image) -> Image.Image:
    rgb = image.convert('RGB')
    thumbnail_height = max(1, round(rgb.height * VISUAL_THUMBNAIL_WIDTH / rgb.width))
    thumbnail = rgb.resize(
        (VISUAL_THUMBNAIL_WIDTH, thumbnail_height),
        Image.Resampling.LANCZOS,
    )
    lookup = [
        min(255, ((value + (VISUAL_CHANNEL_QUANTUM // 2)) // VISUAL_CHANNEL_QUANTUM) * VISUAL_CHANNEL_QUANTUM)
        for value in range(256)
    ]
    return thumbnail.point(lookup * 3)


def visual_thumbnail_sha256(image: Image.Image) -> str:
    thumbnail = build_visual_thumbnail(image)
    return hashlib.sha256(thumbnail.tobytes()).hexdigest()


def assert_visual_baseline(
    page: Page,
    *,
    surface: str,
    theme: str,
    viewport_name: str,
    manifest_path: Path = VISUAL_BASELINE_MANIFEST,
    evidence_root: Path = VISUAL_EVIDENCE_ROOT,
) -> None:
    key = f'{surface}-{theme}-{viewport_name}'
    actual_png = page.screenshot(full_page=True, animations='disabled')

    with Image.open(BytesIO(actual_png)) as image:
        width, height = image.size
        actual_visual_sha = visual_thumbnail_sha256(image)

    baselines: dict[str, dict[str, object]] = {}
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
        if isinstance(payload, dict):
            baselines = {str(name): value for name, value in payload.items() if isinstance(value, dict)}

    if os.environ.get(VISUAL_BASELINE_UPDATE_ENV) == '1':
        baselines[key] = {'visual_sha256': actual_visual_sha, 'width': width, 'height': height}
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(baselines, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )
        return

    assert manifest_path.is_file(), (
        f'visual baseline manifest is missing: {manifest_path}; '
        f'set {VISUAL_BASELINE_UPDATE_ENV}=1 only for an intentional reviewed baseline update'
    )
    assert key in baselines, (
        f'visual baseline is missing for {key}; '
        f'set {VISUAL_BASELINE_UPDATE_ENV}=1 only for an intentional reviewed baseline update'
    )

    expected = baselines[key]
    expected_width = int(expected.get('width', 0))
    expected_height = int(expected.get('height', 0))
    expected_visual_sha = str(expected.get('visual_sha256', ''))

    assert (width, height) == (expected_width, expected_height), (
        f'{key} dimensions changed: expected {expected_width}x{expected_height}, got {width}x{height}'
    )

    if actual_visual_sha == expected_visual_sha:
        return

    evidence_root.mkdir(parents=True, exist_ok=True)
    actual_path = evidence_root / f'{key}-actual.png'
    actual_path.write_bytes(actual_png)
    raise AssertionError(
        f'{key} visual baseline changed: expected visual sha256 {expected_visual_sha}, '
        f'got {actual_visual_sha}; actual screenshot retained at {actual_path}'
    )


def record_visual_audit_finding(
    finding: VisualAuditFinding,
    *,
    evidence_root: Path = VISUAL_EVIDENCE_ROOT,
) -> None:
    evidence_root.mkdir(parents=True, exist_ok=True)
    json_path = evidence_root / 'visual-audit-report.json'
    markdown_path = evidence_root / 'visual-audit-report.md'

    findings: list[dict[str, str]] = []
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding='utf-8'))
        if isinstance(payload, list):
            findings = [
                {str(key): str(value) for key, value in item.items()} for item in payload if isinstance(item, dict)
            ]

    current = {
        'status': finding.status,
        'surface': finding.surface,
        'viewport': finding.viewport,
        'theme': finding.theme,
        'component': finding.component,
        'invariant': finding.invariant,
        'evidence': finding.evidence,
    }
    identity = (finding.surface, finding.viewport, finding.theme, finding.component, finding.invariant)
    findings = [
        item
        for item in findings
        if (
            item.get('surface'),
            item.get('viewport'),
            item.get('theme'),
            item.get('component'),
            item.get('invariant'),
        )
        != identity
    ]
    findings.append(current)
    findings.sort(
        key=lambda item: (
            item.get('surface', ''),
            item.get('viewport', ''),
            item.get('theme', ''),
            item.get('component', ''),
            item.get('invariant', ''),
        )
    )

    json_path.write_text(json.dumps(findings, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    lines = [
        '# KAORI Visual QA Report',
        '',
        '| Status | Surface | Viewport | Theme | Component | Invariant | Evidence |',
        '| --- | --- | --- | --- | --- | --- | --- |',
    ]
    for item in findings:
        values = [
            item.get('status', ''),
            item.get('surface', ''),
            item.get('viewport', ''),
            item.get('theme', ''),
            item.get('component', ''),
            item.get('invariant', ''),
            item.get('evidence', ''),
        ]
        escaped = [value.replace('|', '\\|').replace('\n', ' ') for value in values]
        lines.append('| ' + ' | '.join(escaped) + ' |')
    markdown_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
