from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AuditLogBase(BaseModel):
    action: str
    case_ref: Optional[str] = None
    result: str
    ip_address: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    user_id: Optional[int] = None

class AuditLogResponse(AuditLogBase):
    id: int
    user_id: Optional[int] = None
    timestamp: datetime
    
    model_config = {"from_attributes": True}
