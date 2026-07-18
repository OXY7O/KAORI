from app.integrations.service import _paginate


def test_runtime_overview_pagination_defaults_to_kaori_standard():
    rows = list(range(8))
    page_rows, pagination = _paginate(rows, page=1, per_page=999)
    assert page_rows == [0, 1, 2, 3, 4]
    assert pagination['per_page'] == 5
    assert pagination['allowed_per_page'] == [5, 10, 25, 50]
    assert pagination['has_next'] is True
