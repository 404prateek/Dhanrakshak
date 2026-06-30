"""CLI utility to create the initial admin user.

Usage:
    # Default admin / admin123
    python create_admin.py

    # Custom credentials
    python create_admin.py --employee-id myid --password secret --name "John Doe"
"""
import argparse
import sys
import os

# Ensure backend package is importable when run from any directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.models.user import User  # noqa: F401 — needed for Base.metadata
from app.models import __init__   # noqa: F401 — register all models
from app.core.security import get_password_hash


def create_admin(employee_id: str, password: str, full_name: str) -> None:
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.employee_id == employee_id).first()
        if existing:
            print(f"[INFO] User '{employee_id}' already exists. No changes made.")
            return

        user = User(
            employee_id=employee_id,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            is_active=True,
            role_id=1,
            branch="HQ",
        )
        db.add(user)
        db.commit()
        print(f"[OK] Admin user created — employee_id: {employee_id}")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Failed to create admin: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the initial DhanRakshak admin user")
    parser.add_argument("--employee-id", default="admin",              help="Login ID (default: admin)")
    parser.add_argument("--password",    default="admin123",           help="Password (default: admin123)")
    parser.add_argument("--name",        default="System Administrator", help="Full name")
    args = parser.parse_args()

    create_admin(args.employee_id, args.password, args.name)
