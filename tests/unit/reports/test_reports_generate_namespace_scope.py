from app.reports.generate.service import get_generate_namespace_options


def test_no_selected_cluster_returns_no_namespace_without_database_queries(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError('namespace lookup must not run without selected cluster')

    monkeypatch.setattr('app.reports.generate.service._get_namespace_options_by_cluster', forbidden)
    assert get_generate_namespace_options('') == []
    assert get_generate_namespace_options(' ') == []
