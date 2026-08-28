"""Celery entry point for durable CRM automation jobs."""

import os

from celery import Celery

celery_app = Celery(
    "brokerage_crm",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2"),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=30,
)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=30)
def dispatch_automation(self, event_type: str, payload: dict) -> dict:
    """Provide a durable handoff point for n8n/email/SMS integrations."""
    try:
        # The event is intentionally JSON-only so downstream automation cannot execute code.
        return {"event_type": event_type, "payload": payload, "accepted": True}
    except Exception as error:
        raise self.retry(exc=error) from error
