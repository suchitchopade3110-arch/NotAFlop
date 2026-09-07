"""
Default provider (C6): logs the message and returns True. Acceptable
for now per the task spec — swapping in a real provider (SES, Postmark,
Twilio, ...) is a matter of implementing NotificationProvider.send and
calling services.notifications.service.set_provider() once at startup;
nothing else in the codebase needs to change.
"""
from core.logging import get_logger
from services.notifications.base import NotificationProvider

logger = get_logger("notaflop.notifications.logging_provider")


class LoggingNotificationProvider(NotificationProvider):
    async def send(self, *, to: str, subject: str, body: str, kind: str) -> bool:
        logger.info("notification_sent", to=to, subject=subject, kind=kind, status="logged_not_sent")
        return True
