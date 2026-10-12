from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_first_policy_save_has_no_intermediate_commit() -> None:
    policy = (ROOT / 'app/platform_operations/data_lifecycle/retention/policy_service.py').read_text(encoding='utf-8')
    creator = policy.split('def get_or_create_policy(', 1)[1].split('def update_policy(', 1)[0]
    updater = policy.split('def update_policy(', 1)[1].split('def scheduled_domains(', 1)[0]
    assert 'db.session.add(stored)' in creator
    assert 'db.session.commit()' not in creator
    assert 'policy = get_or_create_policy(domain, fallback)' in updater
    assert 'db.session.commit()' in updater


def test_policy_read_remains_nonmutating() -> None:
    policy = (ROOT / 'app/platform_operations/data_lifecycle/retention/policy_service.py').read_text(encoding='utf-8')
    reader = policy.split('def get_policy(', 1)[1].split('def default_schedule_hour(', 1)[0]
    assert 'query.filter_by(domain=domain).first()' in reader
    assert 'get_or_create_policy(' not in reader
    assert 'db.session.commit()' not in reader
