from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class AlertConsumerProfile:
    asset_type: str
    profile_key: str
    label: str
    required_capabilities: tuple[str, ...]
    optional_capabilities: tuple[str, ...] = ()
    no_match_message: str = ''
    consumer_family: str = 'alerts'
    selector_hint: str = ''


_PROFILES: dict[str, AlertConsumerProfile] = {}
_LOCK = RLock()


def register_alert_consumer_profile(
    profile: AlertConsumerProfile,
    *,
    replace: bool = False,
) -> None:
    asset_type = str(profile.asset_type or '').strip()
    profile_key = str(profile.profile_key or '').strip()
    if not asset_type:
        raise ValueError('Alertmanager consumer profile requires an asset_type.')
    if not profile_key:
        raise ValueError('Alertmanager consumer profile requires a profile_key.')
    if not profile.required_capabilities:
        raise ValueError(f'Alertmanager consumer profile {profile_key!r} requires capability evidence.')
    with _LOCK:
        if asset_type in _PROFILES and not replace:
            raise ValueError(f'Alertmanager consumer profile for {asset_type!r} is already registered.')
        _PROFILES[asset_type] = profile


def get_alert_consumer_profile(asset_type: str) -> AlertConsumerProfile | None:
    return _PROFILES.get(str(asset_type or '').strip())


def registered_alert_consumer_profiles() -> tuple[AlertConsumerProfile, ...]:
    return tuple(_PROFILES[key] for key in sorted(_PROFILES))


_COMMON_REQUIRED = ('alerts_v2', 'alert_labels', 'alertname_label')
_COMMON_OPTIONAL = (
    'severity_label',
    'fingerprint',
    'starts_at',
    'receiver_metadata',
    'summary_annotation',
    'runbook_url',
    'generator_url',
)


for _profile in (
    AlertConsumerProfile(
        asset_type='kubernetes_cluster',
        profile_key='kubernetes-alerts-v1',
        label='Kubernetes Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message=(
            'The selector is valid and no active Kubernetes alert currently matches it. '
            'The binding may remain Ready while payload-label evidence waits for a representative alert.'
        ),
        selector_hint='Use a stable cluster identity label such as cluster=<managed-cluster-identity>.',
    ),
    AlertConsumerProfile(
        asset_type='object_storage_system',
        profile_key='minio-alerts-v1',
        label='MinIO Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message=(
            'The selector is valid and no active MinIO alert currently matches the object-storage asset. '
            'The binding may remain Ready while payload-label evidence waits for a representative alert.'
        ),
        selector_hint='Use the same stable MinIO identity carried by alert rules, for example job or deployment labels.',
    ),
    AlertConsumerProfile(
        asset_type='server',
        profile_key='infrastructure-alerts-v1',
        label='Infrastructure Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message='No active infrastructure alert matched this asset selector.',
        selector_hint='Use a stable host, instance, or asset identity label.',
    ),
    AlertConsumerProfile(
        asset_type='server_group',
        profile_key='infrastructure-group-alerts-v1',
        label='Infrastructure Group Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message='No active infrastructure alert matched this asset-group selector.',
        selector_hint='Use a stable group or service identity label shared by the intended assets.',
    ),
    AlertConsumerProfile(
        asset_type='hci_environment',
        profile_key='platform-alerts-v1',
        label='Platform Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message='No active platform alert matched this environment selector.',
        selector_hint='Use a stable environment or platform identity label.',
    ),
    AlertConsumerProfile(
        asset_type='storage_service',
        profile_key='storage-alerts-v1',
        label='Storage Alerts v1',
        required_capabilities=_COMMON_REQUIRED,
        optional_capabilities=_COMMON_OPTIONAL,
        no_match_message='No active storage alert matched this service selector.',
        selector_hint='Use a stable storage service or deployment identity label.',
    ),
    AlertConsumerProfile(
        asset_type='global',
        profile_key='global-alerts-v1',
        label='Global Alerts v1',
        required_capabilities=('alerts_v2',),
        optional_capabilities=(*_COMMON_REQUIRED[1:], *_COMMON_OPTIONAL),
        no_match_message='The Alertmanager Alerts API is ready; no active alert is currently available for payload enrichment.',
        selector_hint='Global bindings intentionally consume the unscoped alert stream.',
    ),
):
    register_alert_consumer_profile(_profile)
