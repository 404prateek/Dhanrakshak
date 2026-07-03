from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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
    current_user: Any = Depends(require_role(["Admin", "Compliance Manager"]))
) -> Any:
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.post("/", response_model=UserResponse)
def create_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
    current_user: Any = Depends(require_role(["Admin"]))
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

@router.get("/me")
def read_user_me(current_user: ActiveUser) -> Any:
    """Return the hardcoded admin user as a plain JSON dict."""
    return JSONResponse({
        "id": current_user.id,
        "employee_id": current_user.employee_id,
        "full_name": current_user.full_name,
        "branch": current_user.branch,
        "is_active": current_user.is_active,
        "role_id": current_user.role_id,
        "role": {
            "id": current_user.role.id,
            "name": current_user.role.name,
            "description": current_user.role.description,
        },
        "created_at": "2024-01-01T00:00:00Z",
    })

