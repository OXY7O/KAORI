from __future__ import annotations


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def parse_user_agent(user_agent: str | None) -> dict[str, str]:
    """Return safe, presentation-oriented client metadata from a user-agent string."""

    raw_user_agent = (user_agent or '').strip()
    if not raw_user_agent:
        return {
            'browser': 'Unknown browser',
            'os': 'Unknown OS',
            'device': 'Unknown device',
            'summary': 'Unknown browser on Unknown OS',
        }

    user_agent_lower = raw_user_agent.lower()

    if 'edg/' in user_agent_lower or 'edge/' in user_agent_lower:
        browser = 'Microsoft Edge'
    elif 'opr/' in user_agent_lower or 'opera' in user_agent_lower:
        browser = 'Opera'
    elif 'firefox/' in user_agent_lower:
        browser = 'Firefox'
    elif 'chrome/' in user_agent_lower or 'crios/' in user_agent_lower:
        browser = 'Chrome'
    elif 'safari/' in user_agent_lower and 'version/' in user_agent_lower:
        browser = 'Safari'
    elif 'msie' in user_agent_lower or 'trident/' in user_agent_lower:
        browser = 'Internet Explorer'
    else:
        browser = 'Unknown browser'

    if 'windows nt' in user_agent_lower:
        os_name = 'Windows'
    elif 'mac os x' in user_agent_lower or 'macintosh' in user_agent_lower:
        os_name = 'macOS'
    elif 'android' in user_agent_lower:
        os_name = 'Android'
    elif _contains_any(user_agent_lower, ('iphone', 'ipad', 'ipod')):
        os_name = 'iOS'
    elif 'linux' in user_agent_lower:
        os_name = 'Linux'
    elif 'cros' in user_agent_lower:
        os_name = 'ChromeOS'
    else:
        os_name = 'Unknown OS'

    if _contains_any(user_agent_lower, ('mobile', 'iphone', 'android')):
        device = 'Mobile'
    elif _contains_any(user_agent_lower, ('ipad', 'tablet')):
        device = 'Tablet'
    else:
        device = 'Desktop'

    return {
        'browser': browser,
        'os': os_name,
        'device': device,
        'summary': f'{browser} on {os_name}',
    }
