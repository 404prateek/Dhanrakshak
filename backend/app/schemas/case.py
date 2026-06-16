from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DocumentBase(BaseModel):
    file_name: str
    file_type: str

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    case_id: int
    upload_date: datetime
    uploaded_by: Optional[int] = None
    file_path: str
    
    model_config = {"from_attributes": True}

class CaseBase(BaseModel):
    case_ref: str
    applicant_name: str
    property_address: str
    status: Optional[str] = "Pending Review"
    risk_score: Optional[float] = 0.0
    assigned_officer_id: Optional[int] = None

class CaseUpdateStatus(BaseModel):
    status: str

class CaseCreate(CaseBase):
    pass

class CaseResponse(CaseBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    documents: List[DocumentResponse] = []
    
    model_config = {"from_attributes": True}
