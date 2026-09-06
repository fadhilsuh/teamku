"""Transactional email adapter.

Development writes to the process logger and an in-memory outbox so tests and
local onboarding can read invite/reset links without SMTP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger("movon_hr.mailer")


@dataclass
class EmailMessage:
    to: str
    subject: str
    body: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


outbox: list[EmailMessage] = []


def reset_outbox() -> None:
    outbox.clear()


def send_email(to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage(to=to, subject=subject, body=body)
    outbox.append(message)
    logger.info("Email queued to=%s subject=%s\n%s", to, subject, body)
    return message


def last_email_to(address: str) -> EmailMessage | None:
    email = address.strip().lower()
    for message in reversed(outbox):
        if message.to.lower() == email:
            return message
    return None
