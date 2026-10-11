from __future__ import annotations

from types import SimpleNamespace

from app.storage.object_storage.inventory import presentation


def test_canonical_owner_batch_resolves_one_page_in_one_query(monkeypatch) -> None:
    queried: list[str] = []

    class FakeQuery:
        def order_by(self, *_args):
            return self

        def filter(self, *_args):
            return self

        def with_entities(self, *_args):
            return self

        def all(self):
            queried.append('all')
            return [
                (
                    'system-1',
                    SimpleNamespace(integration_type='object_storage', provider_key='minio'),
                    SimpleNamespace(id=5, declared_release='RELEASE.2026-10-01T00-00-00Z'),
                ),
                ('missing-system', None, None),
            ]

    monkeypatch.setattr(presentation, '_system_scope', lambda: FakeQuery())
    owners = presentation._visible_system_owners(['system-1', 'system-1', 'missing-system'])
    assert queried == ['all']
    assert owners['system-1'].provider_key == 'minio'
    assert owners['system-1'].record.id == 5
    assert owners['missing-system'] is None


def test_empty_owner_batch_does_not_read_database(monkeypatch) -> None:
    monkeypatch.setattr(
        presentation, '_system_scope',
        lambda: (_ for _ in ()).throw(AssertionError('unexpected database query')),
    )
    assert presentation._visible_system_owners([]) == {}
