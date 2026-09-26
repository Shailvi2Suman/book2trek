"""
Celery async processing for booking side-effects (confirmation notifications).

Booking must stay off the request's critical path — the caller (and the voice
agent) shouldn't wait on a notification send. When CELERY_BROKER_URL is unset
the task runs eagerly (inline) so everything still works with no broker; point
it at Redis in prod and a worker picks it up.
"""
from __future__ import annotations

import logging

from .. import config as C

log = logging.getLogger("book2trek.tasks")

try:
    from celery import Celery
    _celery = Celery(
        "book2trek",
        broker=C.CELERY_BROKER_URL or "memory://",
        backend="cache+memory://",
    )
    # No broker configured -> run tasks inline so dev/CI needs nothing running.
    _celery.conf.task_always_eager = not bool(C.CELERY_BROKER_URL)
except Exception:  # pragma: no cover
    _celery = None


def _send(kind: str, booking_id: int, detail: str) -> str:
    # In prod this would email/SMS/push; here it logs so the path is observable.
    msg = f"[notify:{kind}] booking={booking_id} {detail}"
    log.info(msg)
    return msg


if _celery is not None:
    @_celery.task(name="book2trek.notify")
    def notify(kind: str, booking_id: int, detail: str = "") -> str:
        return _send(kind, booking_id, detail)

    def send_booking_notification(kind: str, booking_id: int, detail: str = ""):
        """Fire the task; eager mode returns the result inline."""
        return notify.delay(kind, booking_id, detail)
else:  # pragma: no cover
    def send_booking_notification(kind: str, booking_id: int, detail: str = ""):
        return _send(kind, booking_id, detail)
