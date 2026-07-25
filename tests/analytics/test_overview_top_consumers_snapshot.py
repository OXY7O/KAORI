from app.analytics.overview import service


def test_overview_top_consumers_includes_pod_density(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        '_call_optional_snapshot',
        lambda **_: {
            'cpu': [],
            'memory': [],
            'storage': [],
            'pods': [
                {
                    'name': 'platform',
                    'namespace': 'platform',
                    'display_value': '42 pods',
                    'percent': 70,
                }
            ],
            'recommendation_count': 0,
        },
    )

    payload = service._get_top_consumers_snapshot(
        cluster_id='1',
        time_range='24h',
    )

    assert payload['pods'] == [
        {
            'name': 'platform',
            'namespace': 'platform',
            'value': 0,
            'display_value': '42 pods',
            'percent': 70.0,
        }
    ]
