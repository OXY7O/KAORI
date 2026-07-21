from types import SimpleNamespace

from app.integrations.alertmanager.adapter import AlertmanagerRuntimeAdapter
from app.integrations.alertmanager.contracts import ValidationResult, ValidationStep


def _instance(**overrides):
    values = {
        'last_status': 'connected',
        'last_error': None,
        'validation_message': 'Runtime health is available.',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_lightweight_runtime_health_dict_falls_back_to_runtime_diagnostic():
    diagnostics = AlertmanagerRuntimeAdapter._diagnostics(
        _instance(),
        {'version': '0.33.1', 'response_time_ms': 12},
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].key == 'runtime'
    assert diagnostics[0].status == 'success'


def test_serialized_validation_steps_are_supported():
    diagnostics = AlertmanagerRuntimeAdapter._diagnostics(
        _instance(),
        {
            'validation_steps': [
                {
                    'key': 'status_v2',
                    'label': 'Status API',
                    'status': 'failed',
                    'detail': 'Endpoint rejected the request.',
                    'response_time_ms': 25,
                }
            ]
        },
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].key == 'status_v2'
    assert diagnostics[0].category == 'api'
    assert diagnostics[0].severity == 'critical'


def test_canonical_validation_result_is_still_supported():
    result = ValidationResult(
        connected=True,
        label='Alertmanager',
        validation_steps=(
            ValidationStep(
                key='connection',
                label='Connection',
                status='success',
                detail='Connected.',
                response_time_ms=10,
            ),
        ),
    )

    diagnostics = AlertmanagerRuntimeAdapter._diagnostics(_instance(), result)

    assert len(diagnostics) == 1
    assert diagnostics[0].key == 'connection'
    assert diagnostics[0].status == 'success'
