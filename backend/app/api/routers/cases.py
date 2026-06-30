from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.api.deps import get_db, ActiveUser, require_role
from app.models.case import Case, Document
from app.models.user import User
from app.schemas.case import CaseResponse, CaseCreate, DocumentResponse, CaseUpdateStatus
from app.storage.file_manager import FileManager

router = APIRouter()

@router.get("/", response_model=List[CaseResponse])
def read_cases(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: ActiveUser
) -> Any:
    cases = db.query(Case).offset(skip).limit(limit).all()
    return cases

@router.post("/", response_model=CaseResponse)
def create_case(
    *,
    db: Session = Depends(get_db),
    case_in: CaseCreate,
    current_user: User = Depends(require_role(["Underwriter", "Admin"]))
) -> Any:
    case = db.query(Case).filter(Case.case_ref == case_in.case_ref).first()
    if case:
        raise HTTPException(status_code=400, detail="Case ref already exists")
        
    case = Case(
        case_ref=case_in.case_ref,
        applicant_name=case_in.applicant_name,
        property_address=case_in.property_address,
        status=case_in.status,
        risk_score=case_in.risk_score,
        assigned_officer_id=case_in.assigned_officer_id
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case

@router.patch("/{case_id}/status", response_model=CaseResponse)
def update_case_status(
    *,
    db: Session = Depends(get_db),
    case_id: int,
    status_update: CaseUpdateStatus,
    current_user: ActiveUser
) -> Any:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case.status = status_update.status
    case.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(case)
    return case

@router.post("/{case_id}/documents", response_model=DocumentResponse)
async def upload_document(
    *,
    case_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: ActiveUser
) -> Any:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    document = await FileManager.process_and_save_upload(db, file, case_id, current_user.id)
    return document
