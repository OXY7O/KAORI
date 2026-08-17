# app/analytics/kubernetes/common/base_service.py

from __future__ import annotations

from typing import Any

from app.analytics.kubernetes.common.presentation import present_metrics_source_status
from app.integrations.metrics.exceptions import MetricsSourceError


def bytes_to_gib(
    value: float,
) -> float:
    return round(
        value / 1024**3,
        2,
    )


def bytes_to_tib(
    value: float,
) -> float:
    return round(
        value / 1024**4,
        2,
    )


def clamp_percent(
    value: float,
) -> float:
    return max(
        0,
        min(
            value,
            100,
        ),
    )


def safe_percent(
    value: float,
    total: float,
) -> float:
    if not total:
        return 0

    return clamp_percent(
        value / total * 100,
    )


def raw_percent(
    value: float,
    total: float,
) -> float:
    if not total:
        return 0

    return value / total * 100


def safe_round(
    value: float,
    digits: int = 2,
) -> float:
    return round(
        value,
        digits,
    )


class AnalyticsBaseService:
    utilization_service: Any

    def get_metrics_source_scalar(
        self,
        query: str,
    ) -> float:
        result = self.get_metrics_result(
            query,
        )

        if not result:
            return 0

        return self.extract_value(
            result[0],
        )

    def get_metrics_vector_map(
        self,
        query: str,
        label: str,
        secondary_label: str | None = None,
    ) -> dict[str, float]:
        result = self.get_metrics_result(
            query,
        )

        values: dict[str, float] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            primary_value = metric.get(
                label,
                '',
            )

            if (
                not isinstance(
                    primary_value,
                    str,
                )
                or not primary_value
            ):
                continue

            if secondary_label:
                secondary_value = metric.get(
                    secondary_label,
                    '',
                )

                if (
                    not isinstance(
                        secondary_value,
                        str,
                    )
                    or not secondary_value
                ):
                    continue

                key = f'{secondary_value}/{primary_value}'

            else:
                key = primary_value

            values[key] = self.extract_value(
                item,
            )

        return values

    def get_metrics_source_label_map(
        self,
        query: str,
        key_label: str,
        value_label: str,
        secondary_key_label: str | None = None,
    ) -> dict[str, str]:
        result = self.get_metrics_result(
            query,
        )

        values: dict[str, str] = {}

        for item in result:
            metric = item.get(
                'metric',
                {},
            )

            if not isinstance(
                metric,
                dict,
            ):
                continue

            key_value = metric.get(
                key_label,
                '',
            )

            label_value = metric.get(
                value_label,
                '',
            )

            if (
                not isinstance(
                    key_value,
                    str,
                )
                or not key_value
                or not isinstance(
                    label_value,
                    str,
                )
            ):
                continue

            if secondary_key_label:
                secondary_value = metric.get(
                    secondary_key_label,
                    '',
                )

                if (
                    not isinstance(
                        secondary_value,
                        str,
                    )
                    or not secondary_value
                ):
                    continue

                key = f'{secondary_value}/{key_value}'

            else:
                key = key_value

            values[key] = label_value or '-'

        return values

    def get_metrics_result(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        utilization_service = getattr(self, 'utilization_service', None)
        consumer = getattr(utilization_service, 'consumer', None)
        if consumer is None:
            raise MetricsSourceError('A cluster-scoped Metrics Source consumer is required for analytics queries.')

        response = consumer.query(query)
        if not isinstance(response, dict):
            raise MetricsSourceError(f'Metrics Source returned {type(response).__name__}; expected a response mapping.')
        data = response.get('data', {})
        result = data.get('result', []) if isinstance(data, dict) else []
        if not isinstance(result, list):
            raise MetricsSourceError('Metrics Source response data.result is not a list.')
        return [item for item in result if isinstance(item, dict)]

    def extract_value(
        self,
        item: dict[str, Any],
    ) -> float:
        value = item.get(
            'value',
            [
                None,
                0,
            ],
        )

        raw_value: str | int | float

        if isinstance(
            value,
            list,
        ):
            if (
                len(
                    value,
                )
                < 2
            ):
                return 0

            candidate = value[1]

            if not isinstance(
                candidate,
                str | int | float,
            ):
                return 0

            raw_value = candidate

        elif isinstance(
            value,
            str | int | float,
        ):
            raw_value = value

        else:
            return 0

        try:
            return float(
                raw_value,
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    def paginate_rows_with_options(
        self,
        rows: list[dict[str, Any]],
        page: int,
        per_page: int,
        allowed_per_page: list[int],
        default_per_page: int = 5,
    ) -> dict[str, Any]:
        if per_page not in allowed_per_page:
            per_page = default_per_page

        total_items = len(
            rows,
        )

        total_pages = max(
            1,
            (total_items + per_page - 1) // per_page,
        )

        if page < 1:
            page = 1

        if page > total_pages:
            page = total_pages

        start_index = (page - 1) * per_page

        end_index = min(
            start_index + per_page,
            total_items,
        )

        return {
            'rows': rows[start_index:end_index],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'start_item': start_index + 1 if total_items else 0,
                'end_item': end_index,
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'previous_page': max(
                    page - 1,
                    1,
                ),
                'next_page': min(
                    page + 1,
                    total_pages,
                ),
                'per_page_options': allowed_per_page,
            },
        }

    def split_composite_key(
        self,
        key: str,
    ) -> tuple[str, str]:
        if '/' not in key:
            return (
                '',
                key,
            )

        namespace, name = key.split(
            '/',
            1,
        )

        return (
            namespace,
            name,
        )

    def format_cpu(
        self,
        value: float,
    ) -> str:
        if not value:
            return '-'

        if value < 1:
            return f'{safe_round(value * 1000, 0):.0f}m'

        return f'{safe_round(value, 2)}'

    def format_memory_bytes(
        self,
        value: float,
    ) -> str:
        if not value:
            return '-'

        gib_value = bytes_to_gib(
            value,
        )

        if gib_value < 1:
            mib_value = value / 1024**2

            return f'{safe_round(mib_value, 0):.0f} MiB'

        return f'{gib_value} GiB'

    def format_bytes(
        self,
        value: float,
    ) -> str:
        if not value:
            return '-'

        tib_value = bytes_to_tib(
            value,
        )

        if tib_value >= 1:
            return f'{tib_value} TiB'

        gib_value = bytes_to_gib(
            value,
        )

        if gib_value >= 1:
            return f'{gib_value} GiB'

        mib_value = value / 1024**2

        return f'{safe_round(mib_value, 0):.0f} MiB'

    def to_float(
        self,
        value: Any,
    ) -> float:
        if isinstance(
            value,
            int | float,
        ):
            return float(
                value,
            )

        if isinstance(
            value,
            str,
        ):
            try:
                return float(
                    value,
                )
            except ValueError:
                return 0

        return 0

    def get_metrics_source_status(
        self,
    ) -> dict[str, Any]:
        utilization_service = getattr(self, 'utilization_service', None)
        consumer = getattr(utilization_service, 'consumer', None)
        if consumer is None:
            return present_metrics_source_status(
                {
                    'configured': False,
                    'connected': False,
                    'response_time_ms': None,
                    'label': 'Metrics Source Not Configured',
                }
            )

        response = consumer.analytics_status()
        payload = response.payload if isinstance(response.payload, dict) else {}
        response_time = payload.get('response_time_ms')
        observation_degraded = bool(payload.get('observation_degraded'))
        if not response.ok:
            detail = (
                response.diagnostics[0].detail
                if response.diagnostics and response.diagnostics[0].detail
                else (response.diagnostics[0].message if response.diagnostics else 'Metrics Source is unavailable.')
            )
            return present_metrics_source_status(
                {
                    'configured': bool(payload.get('configured', True)),
                    'connected': False,
                    'response_time_ms': response_time,
                    'last_checked_at': payload.get('last_checked_at'),
                    'error': detail,
                }
            )
        return present_metrics_source_status(
            {
                'configured': True,
                'connected': True,
                'response_time_ms': response_time,
                'last_checked_at': payload.get('last_checked_at'),
                'observation_degraded': observation_degraded,
                'last_error': payload.get('last_error'),
            }
        )
