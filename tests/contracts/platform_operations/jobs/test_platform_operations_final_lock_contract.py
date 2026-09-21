from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_platform_operations_final_lock_is_documented_and_release_gated() -> None:
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_2.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_3.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_4.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_5.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_6.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_7.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_8.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V1_9.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V2_0.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V2_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_LOCK_V2_2.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_OVERVIEW_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_1.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_2.md').exists()
    assert (ROOT / 'docs/design/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_LOCK_V1_3.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_3_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_4_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_5_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_6_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_7_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_8_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V1_9_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V2_0_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V2_1_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_FINAL_LOCK_V2_2_AUDIT_2026_08_08.md').exists()
    assert (ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_OVERVIEW_FINAL_LOCK_AUDIT_2026_08_08.md').exists()
    assert (
        ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_AUDIT_2026_08_08.md'
    ).exists()
    assert (
        ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md'
    ).exists()
    assert (
        ROOT / 'docs/design/audits/KAORI_PLATFORM_OPERATIONS_DATA_LIFECYCLE_FINAL_LOCK_V1_2_AUDIT_2026_08_08.md'
    ).exists()
    quality_gate = read('scripts/quality_gate.sh')
    assert 'verify_platform_operations_final_lock.py' in quality_gate
    assert 'run_contract_migration_gate' in quality_gate
    assert "'Contract & Migration Safety'" in quality_gate
    assert 'tests/contracts' in quality_gate
    assert 'tests/migrations' in quality_gate
    assert "-m 'contract or migration'" in quality_gate
    assert 'verify_notification_center_final_lock.py' in quality_gate
    assert 'PASS — KAORI Platform Operations Final Lock v2.2' in read(
        'scripts/verify_platform_operations_final_lock.py'
    )


def test_platform_operations_is_inside_generic_locked_template_scope() -> None:
    verifier = read('scripts/verify_core_workspace_ui_lock.py')
    assert "'app/templates/platform_operations/'" in verifier
    assert "'app/templates/platform_operations/jobs/'" in verifier


def test_platform_operations_uses_shared_tab_contracts() -> None:
    kubernetes = read('app/templates/platform_operations/kubernetes/index.html')
    jobs = read('app/templates/platform_operations/jobs/index.html')
    executions = read('app/templates/platform_operations/jobs/executions/_workspace.html')

    assert 'components/framed_workspace_tabs.html' in kubernetes
    assert 'framed_workspace_tabs.render(' in kubernetes
    assert 'components/framed_workspace_tabs.html' in jobs
    assert 'framed_workspace_tabs.render_navigation(' in jobs
    assert 'components/content_tabs.html' in executions
    assert 'content_tabs.render_links(' in executions
    assert 'components/framed_workspace_tabs.html' not in executions
    assert 'role="tablist"' not in kubernetes
    assert 'role="tablist"' not in jobs
    assert 'role="tablist"' not in executions


def test_namespace_policy_table_does_not_force_horizontal_desktop_scroll() -> None:
    source = read('app/templates/platform_operations/kubernetes/secret_reveal/_namespace_policy_table_content.html')
    assert 'min-w-[980px]' not in source
    assert '<div class="overflow-x-auto">' not in source
    for width in ('w-[38%]', 'w-[16%]', 'w-[20%]', 'w-[26%]'):
        assert width in source


def test_job_registry_filters_are_htmx_owned_without_inline_handlers() -> None:
    source = read('app/templates/platform_operations/jobs/executions/partials/_registry.html')
    assert 'components/table_registry.html' in source
    assert 'table_registry.filter_form' in source
    assert 'table_registry.clear_filters_link' in source
    assert 'table_registry.footer' in source
    assert 'onchange=' not in source
    table_registry = read('app/templates/components/table_registry.html')
    assert 'per_page_options' in table_registry


def test_obsolete_page_local_platform_tabs_remain_deleted() -> None:
    obsolete = 'app/templates/platform_operations/kubernetes/_tabs.html'
    assert not (ROOT / obsolete).exists()
    assert f"'{obsolete}'" in read('scripts/verify_obsolete_files.py')


def test_platform_operations_has_no_accepted_ui_style_debt() -> None:
    import json

    baseline = json.loads(read('docs/architecture/ui-style-debt-baseline.json')).get('files', {})
    assert not [
        path
        for path in baseline
        if path.startswith('app/templates/platform_operations/')
        or path.startswith('app/templates/platform_operations/jobs/')
    ]
