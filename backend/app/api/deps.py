"""FastAPI dependency injectors: DB session, auth, role guards."""
from typing import Annotated, Generator

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.user import User


# ── Database ──────────────────────────────────────────────────────────────────
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]


# ── Auth ──────────────────────────────────────────────────────────────────────
# NOTE: Full JWT auth is intentionally simplified for the internal banking MVP.
# The current implementation uses the first active user (single-tenant mode).
# Replace this with proper JWT decode when multi-user auth is required.
def get_current_user(db: SessionDep) -> User:
    user = db.query(User).filter(User.is_active.is_(True)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active user found. Run create_admin.py first.",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUser) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user


ActiveUser = Annotated[User, Depends(get_current_active_user)]


def require_role(roles: list[str]):
    """Return a FastAPI dependency that enforces role membership."""
    def _checker(current_user: ActiveUser) -> User:
        if current_user.role.name not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {roles}. Your role: {current_user.role.name}",
            )
        return current_user
    return _checker
