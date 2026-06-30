from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db, ActiveUser, require_role
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse])
def read_audit_logs(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role(["Admin", "Auditor", "Compliance Manager"]))
) -> Any:
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs
