from __future__ import annotations

from app.intelligence import rule_exceptions


def test_exception_detail_sql_bounds_history_and_preserves_aggregate_counts(monkeypatch) -> None:
    class FakeQuery:
        def __init__(self):
            self.count_calls = 0
            self.limit_value = None
            self.history_reads = 0

        def filter(self, *_args):
            return self

        def filter_by(self, **_kwargs):
            return self

        def order_by(self, *_args):
            return self

        def count(self):
            self.count_calls += 1
            return 15 if self.count_calls == 1 else 4

        def limit(self, value):
            self.limit_value = value
            return self

        def all(self):
            assert self.limit_value == 12
            self.history_reads += 1
            return []

    from app import create_app

    with create_app('testing').app_context():
        query = FakeQuery()
        monkeypatch.setattr(rule_exceptions.RuleException, 'query', query)
        view = rule_exceptions.build_rule_exception_view('kubernetes.namespace.missing_quota', [])
        assert view['active_count'] == 15
        assert view['expiring_count'] == 4
        assert view['exceptions'] == []
        assert view['owner_options'] == []
        assert query.history_reads == 1
        assert query.limit_value == 12
