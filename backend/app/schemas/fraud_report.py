from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FraudReportBase(BaseModel):
    case_id: int
    risk_score: float
    fraud_category: str
    findings: str
    recommendation: str

class FraudReportCreate(FraudReportBase):
    pass

class FraudReportResponse(FraudReportBase):
    id: int
    generated_at: datetime
    
    model_config = {"from_attributes": True}
