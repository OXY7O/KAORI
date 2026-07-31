import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_forecast_builder_accepts_latest_daily_average_payload_without_flask() -> None:
    original_modules = {
        key: sys.modules.get(key)
        for key in (
            'app',
            'app.dashboards',
            'app.dashboards.kubernetes',
            'app.dashboards.kubernetes.schema',
            'app.dashboards.kubernetes.sections',
            'app.dashboards.kubernetes.sections.forecast',
            'app.dashboards.kubernetes.utils',
        )
    }
    try:
        sys.modules['app'] = types.ModuleType('app')
        sys.modules['app.dashboards'] = types.ModuleType('app.dashboards')
        sys.modules['app.dashboards.kubernetes'] = types.ModuleType('app.dashboards.kubernetes')
        schema = _load_module(
            'app.dashboards.kubernetes.schema',
            ROOT / 'app/dashboards/kubernetes/schema.py',
        )
        utils = types.ModuleType('app.dashboards.kubernetes.utils')
        utils.forecast_insight = lambda items: 'Forecast insight'
        sys.modules[utils.__name__] = utils
        sys.modules['app.dashboards.kubernetes.sections'] = types.ModuleType(
            'app.dashboards.kubernetes.sections'
        )
        forecast = _load_module(
            'app.dashboards.kubernetes.sections.forecast',
            ROOT / 'app/dashboards/kubernetes/sections/forecast.py',
        )

        snapshot = forecast.build_forecast_snapshot(
            context={
                'forecast_payload': {
                    'horizon_days': 90,
                    'items': [
                        {
                            'key': 'memory',
                            'label': 'Memory',
                            'status_label': 'Warning',
                            'projected_percent': 82,
                            'latest_daily_average_percent': 65,
                            'weekly_trend_display': '+2.1% / Week',
                            'historical_points': '0,0 1,1',
                            'forecast_points': '1,1 2,2',
                            'has_data': True,
                        }
                    ],
                }
            },
            unavailable_reason='Unavailable',
        )

        assert isinstance(snapshot, schema.ForecastSnapshot)
        assert snapshot.items[0].latest_daily_average_percent == 65.0
    finally:
        for key, value in original_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value
