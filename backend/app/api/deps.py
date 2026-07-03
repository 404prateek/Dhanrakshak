"""FastAPI dependency injectors: DB session, hardcoded admin, role guards.

Auth is fully bypassed — every request is treated as the hardcoded Admin user.
No JWT tokens, no login, no DB user lookup required.
"""
from typing import Annotated, Generator
from types import SimpleNamespace

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import SessionLocal


# ── Database ──────────────────────────────────────────────────────────────────
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]


# ── Hardcoded Admin ───────────────────────────────────────────────────────────
# Auth is completely bypassed. A single in-memory admin object is returned for
# every request. No DB query, no token validation, no 401 ever raised.
_ADMIN_ROLE = SimpleNamespace(id=1, name="Admin", description="System Administrator")
_ADMIN_USER = SimpleNamespace(
    id=1,
    employee_id="admin",
    full_name="System Administrator",
    is_active=True,
    role_id=1,
    role=_ADMIN_ROLE,
    branch="HQ",
)


def get_current_user() -> object:
    """Always returns the hardcoded admin — no DB, no JWT."""
    return _ADMIN_USER


CurrentUser = Annotated[object, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUser) -> object:
    return current_user


ActiveUser = Annotated[object, Depends(get_current_active_user)]


def require_role(roles: list[str]):
    """Role guard — always passes because the hardcoded user is Admin."""
    def _checker(current_user: ActiveUser) -> object:
        # Admin has access to everything; bypass role check entirely.
        return current_user
    return _checker

