from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db, ActiveUser, require_role
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate
from app.core.security import get_password_hash

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(require_role(["Admin", "Compliance Manager"]))
) -> Any:
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.post("/", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: User = Depends(require_role(["Admin"]))
) -> Any:
    user = db.query(User).filter(User.employee_id == user_in.employee_id).first()
    if user:
        raise HTTPException(status_code=400, detail="User already exists")
        
    user = User(
        employee_id=user_in.employee_id,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role_id=user_in.role_id,
        branch=user_in.branch,
        is_active=user_in.is_active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: ActiveUser) -> Any:
    return current_user
