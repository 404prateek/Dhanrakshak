from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db, ActiveUser
from app.models.investigation_note import InvestigationNote
from app.schemas.investigation_note import InvestigationNoteResponse, InvestigationNoteCreate

router = APIRouter()

@router.get("/case/{case_id}", response_model=List[InvestigationNoteResponse])
def read_investigation_notes(
    *,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: ActiveUser
) -> Any:
    notes = db.query(InvestigationNote).filter(InvestigationNote.case_id == case_id).all()
    return notes

@router.post("/", response_model=InvestigationNoteResponse)
def create_investigation_note(
    *,
    db: Session = Depends(get_db),
    note_in: InvestigationNoteCreate,
    current_user: ActiveUser
) -> Any:
    note = InvestigationNote(
        case_id=note_in.case_id,
        user_id=current_user.id,
        note=note_in.note
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note
