from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_operator_response_uses_structured_clear_workspace() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'data-kaori-operator-response' in detail
    assert 'Recommended Action' in detail
    assert 'Response Context' in detail
    assert 'bg-surface-card' in detail
    assert 'bg-surface-elevated' in detail


def test_alert_escalation_has_pre_save_operational_tips() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    tips = detail.index('data-kaori-alert-escalation-tips')
    save = detail.index('Save Alert Escalation')
    assert tips < save
    assert 'Before saving this escalation' in detail
    assert 'use Manual while ownership or routing is still being validated' in detail
    assert 'Rule + Asset is best for many findings sharing one operational cause' in detail
    assert 'increase Stability Window or Minimum Observations' in detail


def test_risk_exception_explainer_is_compact_and_clear() -> None:
    detail = read('app/templates/intelligence/partials/_catalog_detail_content.html')

    assert 'data-kaori-risk-exception-info' in detail
    assert 'max-w-3xl' in detail
    assert 'rounded-md border border-outline-subtle bg-surface-card px-2.5 py-2' in detail
    assert 'Accepted Risk only suppresses AlertCase promotion while active' in detail
