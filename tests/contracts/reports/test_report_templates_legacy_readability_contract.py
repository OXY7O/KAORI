from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_legacy_template_contracts_fail_safe_without_poisoning_registry() -> None:
    src = (ROOT / 'app/reports/report_templates/service.py').read_text()
    ui = (ROOT / 'app/templates/reports/report_templates/index.html').read_text()
    assert 'def get_custom_template_contract_errors(' in src
    assert 'except ReportContractError:' in src
    assert "'contract_valid': contract_valid" in src
    assert "'can_duplicate': contract_valid" in src
    assert "'can_generate': contract_valid and status == 'active'" in src
    assert 'if contract_valid else' in src
    assert 'Custom template must be repaired before duplication.' in src
    assert 'Contract Needs Review' in ui
    assert '{% if template.can_duplicate %}' in ui
