#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_TEMPLATE_ROOT = ROOT / 'app' / 'templates' / 'reports' / 'pdf'
PDF_CSS_ROOT = ROOT / 'app' / 'static' / 'reports' / 'pdf'
HTML_PDF_ROOT = ROOT / 'app' / 'reports' / 'export' / 'html_pdf'

ANALYTICS_TEMPLATES = {
    'reports/pdf/analytics_overview.html': 'analytics_overview.css',
    'reports/pdf/resource_utilization.html': 'resource_utilization.css',
    'reports/pdf/capacity_analysis.html': 'capacity_analysis.css',
    'reports/pdf/storage_analysis.html': 'storage_analysis.css',
    'reports/pdf/workload_analysis.html': 'workload_analysis.css',
    'reports/pdf/forecast_analysis.html': 'forecast_analysis.css',
    'reports/pdf/top_consumers_analysis.html': 'top_consumers_analysis.css',
    'reports/pdf/alerts_anomalies.html': 'alerts_anomalies.css',
    'reports/pdf/object_storage_analysis.html': 'object_storage_analysis.css',
    'reports/pdf/tenant_governance.html': 'tenant_governance.css',
    'reports/pdf/analytics_unavailable.html': 'analytics_unavailable.css',
}

PRESENTATION_MODULES = (
    'analytics_overview.py',
    'resource_utilization.py',
    'capacity_analysis.py',
    'storage_analysis.py',
    'workload_analysis.py',
    'forecast_analysis.py',
    'top_consumers_analysis.py',
    'alerts_anomalies.py',
    'object_storage_analysis.py',
)

PRESENTATION_OWNERSHIP_PACKAGES = {
    'analytics_overview.py': 'overview',
    'resource_utilization.py': 'utilization',
    'workload_analysis.py': 'workload',
    'forecast_analysis.py': 'forecast',
    'top_consumers_analysis.py': 'top_consumers',
    'alerts_anomalies.py': 'alerts',
}

SECTION_DESCRIPTION_MAX_CHARS = 72

REFERENCE_TEMPLATES = (
    'analytics_overview.html',
    'resource_utilization.html',
    'storage_analysis.html',
    'workload_analysis.html',
    'top_consumers_analysis.html',
    'alerts_anomalies.html',
)


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def read_presentation_ownership(filename: str) -> str:
    sources = [read(HTML_PDF_ROOT / filename)]
    package = PRESENTATION_OWNERSHIP_PACKAGES.get(filename)
    if package:
        package_root = HTML_PDF_ROOT / package
        sources.extend(read(path) for path in sorted(package_root.glob('*.py')))
    return '\n'.join(sources)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    standard_source = read(HTML_PDF_ROOT / 'analytics_publication_standard.py')
    registry_ast = ast.parse(standard_source)
    require(
        "ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v3.0'" in standard_source,
        'Analytics publication standard is not v3.0.',
        errors,
    )
    require(
        "ANALYTICS_CANONICAL_REFERENCE = 'kaori-analytics-publication-v3'" in standard_source,
        'Canonical Analytics publication reference is not v3.',
        errors,
    )
    require(
        "'dynamic_identity_policy': 'reference-register'" in standard_source,
        'Reference-register policy is missing from the shared layout contract.',
        errors,
    )
    require(
        "'chart_label_policy': 'collision-safe-gutter'" in standard_source,
        'Chart label collision policy is missing from the shared layout contract.',
        errors,
    )
    require(
        "'public_reference_policy': 'family-type-date-fingerprint'" in standard_source,
        'Public reference policy is missing from the shared layout contract.',
        errors,
    )
    for token in (
        "'section_description_policy': 'concise-helper-max-72'",
        "'paired_layout_policy': 'symmetric-50-50-or-stack'",
        "'peer_alignment_policy': 'shared-title-helper-body-rows'",
        "'peer_section_flow_policy': 'block-grid-owned-alignment'",
        "'peer_helper_slot': '7mm'",
        "'section_spacing_policy': '5.6mm'",
        "'first_section_clearance_policy': 'canonical-gap-even-after-non-section-block'",
        "'top_level_flow_policy': 'publication-block-owns-outer-gap'",
        "'publication_stack_policy': 'outer-5.6mm-inner-5.6mm'",
        "'chart_spacing_policy': 'internal-only-no-next-section-clearance'",
        "'shared_component_spacing_policy': 'summary-cards-and-chart-legends-global'",
        "'paired_section_clearance_policy': 'single-5.6mm-section-gap-no-double-spacing'",
        "'visual_box_policy': 'locked-size-tokens-content-scales-inside'",
        "'footer_safe_zone': '18mm'",
        "'paragraph_spacing_policy': '2.2mm'",
        "'global_rhythm_owner_policy': 'shared-stylesheet-only'",
        "'dense_page_policy': 'compact-internal-chrome-never-typography'",
        "'chart_identity_policy': 'stable-reference-codes-only'",
        "'dynamic_page_policy': 'content-budgeted'",
        "'section_continuation_policy': 'same-section-only'",
        "'table_overflow_policy': 'chunk-with-repeated-header'",
        "'reference_layout_policy': 'two-column-or-stack'",
        "'typography_scaling_policy': 'never-for-density'",
        "'dynamic_pair_policy': 'density-selects-50-50-or-stack'",
    ):
        require(token in standard_source, f'Missing Analytics rhythm policy: {token}', errors)

    registry: dict[str, str] | None = None
    for node in registry_ast.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == 'ANALYTICS_TEMPLATE_STYLESHEETS'
        ):
            registry = ast.literal_eval(node.value)
            break
    require(
        registry == ANALYTICS_TEMPLATES,
        'Analytics template/CSS registry does not exactly match the canonical v3 set.',
        errors,
    )

    shared_css = read(PDF_CSS_ROOT / 'analytics_publication.css')
    compact_css = re.sub(r'\s+', '', shared_css)
    for token in (
        'KAORI Analytics PDF Publication Standard v3.0',
        'font-family:"Inter Analytics"',
        'font-size:8pt',
        'line-height:1.44',
        'table-layout:fixed',
        'overflow-wrap:break-word',
        '.identity-register',
        '.page-footer',
    ):
        require(
            token.replace(' ', '') in compact_css
            if token != 'KAORI Analytics PDF Publication Standard v3.0'
            else token in shared_css,
            f'Missing shared CSS contract token: {token}',
            errors,
        )
    require('text-overflow:ellipsis' not in compact_css, 'Evidence CSS must not use ellipsis.', errors)
    require('word-break:break-all' not in compact_css, 'Evidence CSS must not use break-all.', errors)
    require('font-size:7pt' in compact_css, 'Canonical report table body size must remain 7pt.', errors)
    for token in (
        'KAORI Analytics Publication Rhythm Lock',
        '--analytics-type-section:10.2pt',
        '--analytics-type-subheading:8.2pt',
        '--analytics-type-body:8pt',
        '--analytics-type-support:6.65pt',
        '--analytics-rhythm-title-description:1.45mm',
        '--analytics-rhythm-description-content:3mm',
        '--analytics-rhythm-paragraph:2.2mm',
        '--analytics-rhythm-register-reference:3.6mm',
        '--analytics-rhythm-section:5.6mm',
        '--analytics-rhythm-component:3.6mm',
        'KAORI Analytics Publication R9 - section clearance lock',
        'KAORI Analytics Publication R11 - top-level flow ownership lock',
        '.publication-stack',
        '.summary-box-grid',
        '.chart-legend',
        '--analytics-rhythm-pair-clearance:0mm',
        '--analytics-footer-safe-zone:18mm',
        '--analytics-visual-pair-height:50mm',
        '--analytics-visual-distribution-height:48mm',
        '--analytics-visual-wide-height:66mm',
    ):
        require(
            token.replace(' ', '') in compact_css
            if token != 'KAORI Analytics Publication Rhythm Lock'
            else token in shared_css,
            f'Missing shared publication rhythm token: {token}',
            errors,
        )

    require(
        'chart-to-section-gap' not in shared_css,
        'Legacy chart-to-section spacing must not be owned by shared CSS.',
        errors,
    )
    require(
        'chart-to-section-gap'
        not in (ROOT / 'app/static/reports/pdf/resource_utilization.css').read_text(encoding='utf-8'),
        'Resource Utilization must not own inter-section clearance through chart internals.',
        errors,
    )

    require(
        'KAORI Analytics Publication R6 - Clean Sweep' in shared_css,
        'Shared Analytics clean-sweep ownership block is missing.',
        errors,
    )
    for token in (
        'KAORI Analytics Publication R7 - Global Adaptive Publication Engine',
        '.publication-pair',
        '.publication-pair.is-stacked',
        '.publication-continuation',
        '.publication-visual',
    ):
        require(token in shared_css, f'Missing dynamic publication CSS token: {token}', errors)

    overview_css = read(PDF_CSS_ROOT / 'analytics_overview.css')
    overview_compact = re.sub(r'\s+', '', overview_css)
    for token in ('max-width:100%', '.report-use-advisory', '.fresh-table'):
        require(token in overview_compact, f'Missing Analytics Overview layout token: {token}', errors)

    component = read(PDF_TEMPLATE_ROOT / 'components' / 'analytics_publication.html')
    require('macro identity_register' in component, 'Shared identity_register macro is missing.', errors)
    require(
        'complete identities' in component.lower() or 'identity-register' in component,
        'Shared publication component does not expose the identity register.',
        errors,
    )

    for template_name, css_name in ANALYTICS_TEMPLATES.items():
        template_path = ROOT / 'app' / 'templates' / template_name
        css_path = PDF_CSS_ROOT / css_name
        require(template_path.exists(), f'Missing canonical Analytics template: {template_name}', errors)
        require(css_path.exists(), f'Missing canonical Analytics stylesheet: {css_name}', errors)
        if css_path.exists() and css_name != 'analytics_unavailable.css':
            report_css = read(css_path)
            direct_section = re.compile(
                r'\.page[-\w]+\s+\.content-section\s*\{[^}]*margin-top\s*:',
                flags=re.DOTALL,
            )
            direct_body = re.compile(
                r'\.page[-\w]+\s+\.section-body\s*\{[^}]*margin-top\s*:',
                flags=re.DOTALL,
            )
            global_subheading = re.compile(r'(?m)^\.subheading\s*\{[^}]*margin\s*:')
            require(
                not direct_section.search(report_css) and not direct_body.search(report_css),
                f'Report CSS overrides canonical top-level section rhythm: {css_name}',
                errors,
            )
            require(
                not global_subheading.search(report_css),
                f'Report CSS overrides canonical subheading rhythm: {css_name}',
                errors,
            )
            split_ratio = re.compile(r'[^{}]*-split[^{}]*\{[^}]*grid-template-columns\s*:', flags=re.DOTALL)
            require(
                not split_ratio.search(report_css),
                f'Peer column ratios must be owned by shared publication CSS: {css_name}',
                errors,
            )
        if template_path.exists():
            source = read(template_path)
            require(
                'components/analytics_publication.html' in source,
                f'{template_name} does not use the canonical publication component.',
                errors,
            )
            require(
                'kaori-analytics-publication' in source,
                f'{template_name} is missing the Analytics publication root class.',
                errors,
            )
            for class_value in re.findall(r'class="([^"]*\btwo-column\b[^"]*)"', source):
                require(
                    'publication-pair' in class_value.split(),
                    f'{template_name} two-column layout bypasses publication-pair.',
                    errors,
                )
            section_pattern = re.compile(
                r"(?:ui\.)?section\(\s*'([^']+)'(?:\s*,\s*'([^']*)')?",
                flags=re.MULTILINE,
            )
            for title, subtitle in section_pattern.findall(source):
                require(
                    bool(subtitle.strip()),
                    f'Missing section description in {template_name}: {title}',
                    errors,
                )
                require(
                    len(subtitle) <= SECTION_DESCRIPTION_MAX_CHARS,
                    f'Section description exceeds {SECTION_DESCRIPTION_MAX_CHARS} characters in {template_name}: {title}',
                    errors,
                )

    for legacy in (
        PDF_TEMPLATE_ROOT / 'report.html',
        PDF_TEMPLATE_ROOT / 'components' / '_reporting_standard.html',
        PDF_CSS_ROOT / 'report.css',
        PDF_CSS_ROOT / 'reporting_standard.css',
    ):
        require(not legacy.exists(), f'Legacy PDF publication path still exists: {legacy.relative_to(ROOT)}', errors)

    for filename in PRESENTATION_MODULES:
        source = read_presentation_ownership(filename)
        require("'presentation_version': 'v3.0-" in source, f'{filename} is not marked as a v3.0 presentation.', errors)
        require(
            "table_policy='concise-register-plus-reference'" in source,
            f'{filename} does not use concise register plus reference policy.',
            errors,
        )

    for filename in REFERENCE_TEMPLATES:
        source = read(PDF_TEMPLATE_ROOT / filename)
        require(
            'identity-register' in source or 'identity_register(' in source,
            f'{filename} does not preserve dynamic technical identities in a reference register.',
            errors,
        )

    chart_helper = read(HTML_PDF_ROOT / 'chart_labels.py')
    require('def resolve_vertical_labels(' in chart_helper, 'Chart collision resolver is missing.', errors)
    for filename in ('forecast_analysis.py', 'resource_utilization.py'):
        source = read_presentation_ownership(filename)
        require(
            'resolve_vertical_labels' in source,
            f'{filename} does not use the collision-safe chart label resolver.',
            errors,
        )
    capacity_chart_source = read(HTML_PDF_ROOT / 'capacity' / 'charts.py')
    require(
        'resolve_vertical_labels' in capacity_chart_source,
        'capacity/charts.py does not use the collision-safe chart label resolver.',
        errors,
    )

    resource_source = read_presentation_ownership('resource_utilization.py')
    overview_source = read_presentation_ownership('analytics_overview.py')
    require(
        '/ 1024 ** 3' in resource_source or '/ 1024**3' in resource_source,
        'Resource Utilization does not normalize byte memory values to GiB.',
        errors,
    )
    require(
        '/ 1024 ** 3' in overview_source or '/ 1024**3' in overview_source,
        'Analytics Overview does not normalize byte memory values to GiB.',
        errors,
    )

    reference_source = read(ROOT / 'app' / 'reports' / 'reference.py')
    for code in ('AOV', 'RUT', 'CAP', 'STO', 'WLA', 'TNG', 'FCT', 'TPC', 'ALA'):
        require(f"'{code}'" in reference_source, f'Missing Analytics report type code: {code}', errors)
    require(
        "return f'KAORI-{family_code}-{type_code}-{date_code}-{fingerprint}'" in reference_source,
        'Public report reference convention is not canonical.',
        errors,
    )

    builder_source = read(HTML_PDF_ROOT / 'builder.py')
    require(
        "template_name = 'reports/pdf/analytics_unavailable.html'" in builder_source,
        'Unavailable Analytics publication is not the canonical fallback.',
        errors,
    )
    require('build_report_reference' in builder_source, 'Builder does not use public report references.', errors)

    docs = read(ROOT / 'docs' / 'reports' / 'kaori-analytics-pdf-publication-standard-v3.md')
    for value in (
        'kaori-analytics-pdf-v3.0',
        'Concise register',
        'Reference register',
        'collision-safe',
        'same evidence series and denominator',
        'Raw ISO timestamps with microseconds are prohibited',
        'fixed evidence tables are the smallest readable role',
        'Family editorial rhythm lock (2026-08-25)',
        'Section helper descriptions should remain at or below 72 characters',
        'stack the blocks vertically',
        'KAORI-{FAMILY}-{TYPE}-{YYYYMMDD}-{FINGERPRINT}',
    ):
        require(value in docs, f'Publication documentation is missing: {value}', errors)

    baseline_path = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
    if baseline_path.exists():
        baseline = json.loads(read(baseline_path))
        require(
            'app/templates/reports/pdf/report.html' not in baseline.get('files', {}),
            'Deleted legacy report template remains in UI style debt baseline.',
            errors,
        )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI Analytics PDF Publication v3 audit passed: one canonical publication family, '
        'reference-safe dynamic tables, collision-safe charts, normalized typography and public references.'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
