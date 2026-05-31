"""
Webhook delivery service.

fire_event() is called synchronously but delivers the HTTP POST in a
FastAPI BackgroundTask so the API response isn't blocked by webhook latency.

Payload shape (same for all events):
  {
    "event": "status.transition",
    "timestamp": "2026-05-31T12:00:00Z",
    "org_id": "org_demo",
    "data": { ... event-specific fields ... }
  }

Signature: if the webhook has a secret, X-SOW-Signature is set to
  sha256_hmac(secret, json_body_bytes).hex()
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.webhook import Webhook

logger = logging.getLogger(__name__)


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(url: str, secret: str | None, payload: dict, webhook_id: str) -> None:
    body = json.dumps(payload, default=str).encode()
    headers = {"Content-Type": "application/json", "X-SOW-Event": payload["event"]}
    if secret:
        headers["X-SOW-Signature"] = _sign(secret, body)

    try:
        resp = httpx.post(url, content=body, headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info("Webhook %s delivered to %s → %d", webhook_id, url, resp.status_code)
    except Exception as exc:
        logger.warning("Webhook %s delivery to %s failed: %s", webhook_id, url, exc)


def fire_event(
    db: Session,
    background_tasks: BackgroundTasks,
    org_id: str,
    event: str,
    data: dict,
) -> int:
    """Queue delivery for all active webhooks subscribed to this event. Returns count fired."""
    hooks = (
        db.query(Webhook)
        .filter(
            Webhook.org_id == org_id,
            Webhook.is_active == True,  # noqa: E712
        )
        .all()
    )

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "org_id": org_id,
        "data": data,
    }

    fired = 0
    for hook in hooks:
        if event not in (hook.events or []):
            continue

        # Update last_fired_at optimistically (don't wait for delivery)
        hook.last_fired_at = datetime.now(timezone.utc)
        db.commit()

        background_tasks.add_task(_deliver, hook.url, hook.secret, payload, hook.id)
        fired += 1

    return fired
