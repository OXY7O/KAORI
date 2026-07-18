from app.prometheus.query_profiles.feature_contracts import _usable_rows


def test_aggregate_vector_without_labels_is_usable():
    usable, labels, summary = _usable_rows([
        {'metric': {}, 'value': [1720000000, '4']},
    ])
    assert usable == 1
    assert labels == set()
    assert 'value 4' in summary


def test_non_numeric_samples_are_not_usable():
    usable, labels, summary = _usable_rows([
        {'metric': {'node': 'worker-01'}, 'value': [1720000000, 'NaN']},
    ])
    assert usable == 0
    assert labels == {'node'}
    assert summary is None
