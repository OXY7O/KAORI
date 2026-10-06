from __future__ import annotations

from dataclasses import dataclass

from app.definitions.integration_registry import integration_provider_document
from app.definitions.validation import optional_str, require_list, require_mapping, require_str, string_tuple


@dataclass(frozen=True, slots=True)
class MetricsProviderSupportPresentation:
    minimum_version: str
    minimum_label: str
    recommended_version: str
    recommended_label: str
    support_band: str
    current_band: str
    support_label: str
    support_tone: str
    capability_summary: str
    validation_basis: str


@dataclass(frozen=True, slots=True)
class MetricsProviderDefinition:
    key: str
    label: str
    description: str
    adapter_key: str
    query_language: str
    default_query_horizon: str
    version_detection_mode: str
    endpoint_placeholder: str
    icon: str
    endpoint_capabilities: tuple[str, ...] = ()
    compatibility_profile_options: tuple[tuple[str, str], ...] = ()
    support_presentation: MetricsProviderSupportPresentation | None = None


def _load_provider_definitions() -> dict[str, MetricsProviderDefinition]:
    document = integration_provider_document('metrics_source')
    definitions: dict[str, MetricsProviderDefinition] = {}
    for index, raw in enumerate(require_list(document.get('provider_kinds'), 'metrics_source.provider_kinds')):
        item = require_mapping(raw, f'metrics_source.provider_kinds[{index}]')
        options: list[tuple[str, str]] = []
        for option_index, raw_option in enumerate(item.get('compatibility_profile_options') or ()):
            option = require_mapping(
                raw_option,
                f'metrics_source.provider_kinds[{index}].compatibility_profile_options[{option_index}]',
            )
            options.append(
                (
                    require_str(
                        option,
                        'value',
                        f'metrics_source.provider_kinds[{index}].compatibility_profile_options[{option_index}]',
                    ),
                    require_str(
                        option,
                        'label',
                        f'metrics_source.provider_kinds[{index}].compatibility_profile_options[{option_index}]',
                    ),
                )
            )
        support_raw = item.get('support_presentation')
        support = None
        if support_raw is not None:
            support_item = require_mapping(support_raw, f'metrics_source.provider_kinds[{index}].support_presentation')
            support = MetricsProviderSupportPresentation(
                minimum_version=require_str(
                    support_item, 'minimum_version', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                minimum_label=require_str(
                    support_item, 'minimum_label', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                recommended_version=require_str(
                    support_item, 'recommended_version', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                recommended_label=require_str(
                    support_item, 'recommended_label', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                support_band=require_str(
                    support_item, 'support_band', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                current_band=require_str(
                    support_item, 'current_band', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                support_label=require_str(
                    support_item, 'support_label', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                support_tone=require_str(
                    support_item, 'support_tone', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                capability_summary=require_str(
                    support_item, 'capability_summary', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
                validation_basis=require_str(
                    support_item, 'validation_basis', f'metrics_source.provider_kinds[{index}].support_presentation'
                ),
            )
        definition = MetricsProviderDefinition(
            key=require_str(item, 'key', f'metrics_source.provider_kinds[{index}]').lower(),
            label=require_str(item, 'label', f'metrics_source.provider_kinds[{index}]'),
            description=optional_str(item, 'description', f'metrics_source.provider_kinds[{index}]') or '',
            adapter_key=require_str(item, 'adapter_key', f'metrics_source.provider_kinds[{index}]').lower(),
            query_language=require_str(item, 'query_language', f'metrics_source.provider_kinds[{index}]').lower(),
            default_query_horizon=require_str(
                item, 'default_query_horizon', f'metrics_source.provider_kinds[{index}]'
            ).lower(),
            version_detection_mode=require_str(
                item,
                'version_detection_mode',
                f'metrics_source.provider_kinds[{index}]',
            ).lower(),
            endpoint_placeholder=require_str(
                item,
                'endpoint_placeholder',
                f'metrics_source.provider_kinds[{index}]',
            ),
            icon=require_str(item, 'icon', f'metrics_source.provider_kinds[{index}]'),
            endpoint_capabilities=string_tuple(
                item.get('endpoint_capabilities'),
                f'metrics_source.provider_kinds[{index}].endpoint_capabilities',
            ),
            compatibility_profile_options=tuple(options),
            support_presentation=support,
        )
        definitions[definition.key] = definition
    return definitions


PROVIDERS = _load_provider_definitions()


def provider_definition(provider_key: str) -> MetricsProviderDefinition:
    key = str(provider_key or '').strip().lower()
    try:
        return PROVIDERS[key]
    except KeyError as exc:
        raise ValueError(f'Unsupported metrics source provider: {provider_key!r}.') from exc


def provider_definitions() -> tuple[MetricsProviderDefinition, ...]:
    return tuple(sorted(PROVIDERS.values(), key=lambda item: item.label.casefold()))


def provider_options() -> list[dict[str, str]]:
    return [
        {'value': item.key, 'label': item.label}
        for item in sorted(PROVIDERS.values(), key=lambda item: item.label.casefold())
    ]


def provider_keys() -> tuple[str, ...]:
    return tuple(sorted(PROVIDERS))
