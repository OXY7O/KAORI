from app.integrations.alertmanager.profiles.base import AlertmanagerProfile

PROFILE = AlertmanagerProfile(
    key='alertmanager-v0-33',
    version_constraint='>=0.27,<0.34',
    support_level='current',
    required_capabilities=('status_v2', 'alerts_v2', 'silences_v2'),
)
