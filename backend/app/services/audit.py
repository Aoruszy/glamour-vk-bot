from sqlalchemy.orm import Session

from app.core.enums import ActorRole
from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    *,
    user_role: ActorRole,
    action: str,
    entity_type: str,
    entity_id: int | None,
    details: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_role=user_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(entry)
    db.flush()
    return entry
