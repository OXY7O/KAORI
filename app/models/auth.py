from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def parse_user_agent(user_agent: str | None) -> dict[str, str]:
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


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuthLoginEvent(db.Model):
    __tablename__ = 'auth_login_events'

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
        index=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id'),
        nullable=True,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='database',
        index=True,
    )

    success: Mapped[bool] = mapped_column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        db.String(100),
        nullable=False,
        index=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        db.String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    @property
    def user_agent_info(self) -> dict[str, str]:
        return parse_user_agent(self.user_agent)

    @property
    def user_agent_summary(self) -> str:
        return self.user_agent_info['summary']

    @property
    def user_agent_browser(self) -> str:
        return self.user_agent_info['browser']

    @property
    def user_agent_os(self) -> str:
        return self.user_agent_info['os']

    @property
    def user_agent_device(self) -> str:
        return self.user_agent_info['device']
