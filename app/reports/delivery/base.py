from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.models.report import Report


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    channel: str
    status: str
    message: str

    @property
    def success(self) -> bool:
        return self.status == 'success'

    def to_dict(self) -> dict[str, str]:
        return {'channel': self.channel, 'status': self.status, 'message': self.message}


class ReportDeliveryChannel(Protocol):
    key: str

    def deliver(self, report: Report) -> DeliveryResult: ...
