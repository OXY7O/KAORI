ENVIRONMENTS = [
    ('dev', 'Development'),
    ('stg', 'Staging'),
    ('prd', 'Production'),
]

_ENVIRONMENT_LABELS = {
    'dev': 'Development',
    'development': 'Development',
    'stg': 'Staging',
    'stage': 'Staging',
    'staging': 'Staging',
    'prd': 'Production',
    'prod': 'Production',
    'production': 'Production',
    'uat': 'UAT',
    'qa': 'QA',
    'test': 'Testing',
    'testing': 'Testing',
    'dr': 'Disaster Recovery',
    'drc': 'Disaster Recovery',
    'disaster-recovery': 'Disaster Recovery',
    'sandbox': 'Sandbox',
    'lab': 'Lab',
}


def get_environment_label(value: str | None, *, empty: str = 'Not specified') -> str:
    """Return a user-facing environment label without changing the stored value."""
    normalized = (value or '').strip()
    if not normalized:
        return empty

    return _ENVIRONMENT_LABELS.get(normalized.lower(), normalized)
