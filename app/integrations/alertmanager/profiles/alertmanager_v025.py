from app.integrations.alertmanager.profiles.base import AlertmanagerProfile

PROFILE = AlertmanagerProfile(
    key='alertmanager-v0-25',
    version_constraint='>=0.25,<0.27',
    support_level='legacy',
    required_capabilities=('status_v2', 'alerts_v2', 'silences_v2'),
    known_limitations=('Legacy runtime line; validate observed payload metadata before enabling advanced analytics.',),
)
