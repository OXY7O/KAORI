from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_development_inventory_worker_has_two_slots_and_fair_prefetch():
    compose = read('.devcontainer/compose.devcontainer.yml')
    assert '--queues=inventory' in compose
    assert '--concurrency="$${INVENTORY_WORKER_CONCURRENCY:-2}"' in compose
    assert '--prefetch-multiplier="$${INVENTORY_WORKER_PREFETCH_MULTIPLIER:-1}"' in compose
    assert '--max-tasks-per-child="$${INVENTORY_MAX_TASKS_PER_CHILD:-50}"' in compose


def test_production_inventory_worker_uses_same_inventory_specific_contract():
    compose = read('compose.production.yml')
    assert '--queues=inventory' in compose
    assert '--concurrency="$${INVENTORY_WORKER_CONCURRENCY:-2}"' in compose
    assert '--prefetch-multiplier="$${INVENTORY_WORKER_PREFETCH_MULTIPLIER:-1}"' in compose
    assert '--max-tasks-per-child="$${INVENTORY_MAX_TASKS_PER_CHILD:-50}"' in compose
    assert 'CELERY_WORKER_CONCURRENCY' not in compose


def test_inventory_worker_environment_examples_are_documented():
    for path in ('.env.example', '.env.production.example'):
        env = read(path)
        assert 'INVENTORY_WORKER_CONCURRENCY=2' in env
        assert 'INVENTORY_WORKER_PREFETCH_MULTIPLIER=1' in env
        assert 'INVENTORY_MAX_TASKS_PER_CHILD=50' in env
