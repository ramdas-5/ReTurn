"""Append-only audit trail. Callers commit the surrounding transaction."""
from __future__ import annotations

from flask import g, has_request_context, request

from ..extensions import db
from ..models import AuditLog


def audit(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    *,
    actor=None,
    summary: str = "",
    reason: str | None = None,
    event_metadata: dict | None = None,
) -> AuditLog:
    actor = actor if actor is not None else getattr(g, "user", None)
    ip = None
    agent = None
    if has_request_context():
        forwarded = request.headers.get("X-Forwarded-For", "")
        ip = (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or None
        agent = (request.user_agent.string or "")[:255] or None
    entry = AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_role=getattr(actor, "role", None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:600] or action,
        reason=(reason or None),
        ip_address=ip,
        user_agent=agent,
        event_metadata=event_metadata or {},
    )
    db.session.add(entry)
    return entry
