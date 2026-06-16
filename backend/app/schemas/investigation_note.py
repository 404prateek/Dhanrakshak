from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InvestigationNoteBase(BaseModel):
    case_id: int
    note: str

class InvestigationNoteCreate(InvestigationNoteBase):
    pass

class InvestigationNoteResponse(InvestigationNoteBase):
    id: int
    user_id: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
