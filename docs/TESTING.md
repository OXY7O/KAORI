# KAORI Testing

The previous automated test suite has intentionally been removed while the application structure is being stabilized.

Testing support remains available through `pytest`, `pytest-flask`, and `pytest-cov` in `requirements/dev.in`. New tests should be added under `tests/` when the test strategy is rebuilt.

A dedicated test database is not provisioned automatically by the current Dev Container. When automated tests are reintroduced, add an isolated test-database workflow rather than running tests against the development database.
