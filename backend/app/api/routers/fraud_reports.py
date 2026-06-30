from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, ActiveUser, require_role
from app.models.user import User
from app.models.fraud_report import FraudReport
from app.schemas.fraud_report import FraudReportResponse, FraudReportCreate

router = APIRouter()

@router.get("/case/{case_id}", response_model=List[FraudReportResponse])
def read_fraud_reports(
    *,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: ActiveUser
) -> Any:
    reports = db.query(FraudReport).filter(FraudReport.case_id == case_id).all()
    return reports

@router.post("/", response_model=FraudReportResponse)
def create_fraud_report(
    *,
    db: Session = Depends(get_db),
    report_in: FraudReportCreate,
    current_user: User = Depends(require_role(["Fraud Analyst", "Investigator", "Admin"]))
) -> Any:
    report = FraudReport(
        case_id=report_in.case_id,
        risk_score=report_in.risk_score,
        fraud_category=report_in.fraud_category,
        findings=report_in.findings,
        recommendation=report_in.recommendation
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
