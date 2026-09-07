"""
Notification provider interface (C6). Everything in
services/notifications/service.py composes a message and hands it to
whatever provider is currently configured — a real email/SMS/push
integration is a matter of implementing this one method and calling
set_provider(), nothing else in the codebase changes.
"""
from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    @abstractmethod
    async def send(self, *, to: str, subject: str, body: str, kind: str) -> bool:
        """Returns True if the message was accepted for sending (not a
        delivery guarantee). `kind` is a short machine-readable tag
        (e.g. 'magic_link', 'snapshot_digest', 'criteria_deadline') for
        providers that want to route or template by notification type."""
        ...
