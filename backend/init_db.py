#!/usr/bin/env python3
"""
init_db.py — Railway one-time database initialization script.

Run this as a Railway "one-off" command after first deploy:
    python backend/init_db.py

Or set it as the Railway start command for the FIRST deploy only:
    python backend/init_db.py && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

Environment variables required:
    DATABASE_URL   — e.g. postgresql://user:pass@host:5432/dhanrakshak (from Railway Postgres addon)
    ADMIN_PASSWORD — optional, defaults to 'admin123' (CHANGE IN PRODUCTION!)
    ADMIN_ID       — optional, defaults to 'admin'
"""
import sys
import os

# Ensure the project root is in the Python path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if os.path.join(_ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "backend"))

# Also support running from /app (Docker WORKDIR)
for p in ["/app", "/app/backend"]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.models import __init__ as _models_init  # noqa — registers all models
from app.models.user import User, Role
from app.core.security import get_password_hash

print("=" * 60)
print("DhanRakshak — Database Initialization")
print("=" * 60)

# 1. Create all tables
print("[1/3] Creating database tables...")
Base.metadata.create_all(bind=engine)
print("      Tables created (or already exist).")

# 2. Seed roles
print("[2/3] Seeding roles...")
db = SessionLocal()
try:
    roles = [
        Role(id=1, name="Admin",              description="System Administrator"),
        Role(id=2, name="Underwriter",        description="Case Underwriter"),
        Role(id=3, name="Auditor",            description="Audit Team"),
        Role(id=4, name="Compliance Manager", description="Compliance Manager"),
        Role(id=5, name="Investigator",       description="Fraud Investigator"),
    ]
    inserted = 0
    for role in roles:
        if not db.query(Role).filter(Role.id == role.id).first():
            db.add(role)
            inserted += 1
    db.commit()
    print(f"      {inserted} role(s) inserted, {len(roles) - inserted} already existed.")
except Exception as e:
    db.rollback()
    print(f"      [ERROR] Role seeding failed: {e}")
    sys.exit(1)
finally:
    db.close()

# 3. Create admin user
print("[3/3] Creating admin user...")
admin_id  = os.environ.get("ADMIN_ID",       "admin")
admin_pw  = os.environ.get("ADMIN_PASSWORD", "admin123")
admin_name = os.environ.get("ADMIN_NAME",    "System Administrator")

if admin_pw == "admin123":
    print("      ⚠️  WARNING: Using default password 'admin123'. Set ADMIN_PASSWORD env var!")

db = SessionLocal()
try:
    existing = db.query(User).filter(User.employee_id == admin_id).first()
    if existing:
        print(f"      Admin '{admin_id}' already exists — skipping.")
    else:
        user = User(
            employee_id=admin_id,
            full_name=admin_name,
            hashed_password=get_password_hash(admin_pw),
            is_active=True,
            role_id=1,
            branch="HQ",
        )
        db.add(user)
        db.commit()
        print(f"      ✅ Admin created — employee_id: '{admin_id}'")
except Exception as e:
    db.rollback()
    print(f"      [ERROR] Admin creation failed: {e}")
    sys.exit(1)
finally:
    db.close()

print("=" * 60)
print("✅ Database initialization complete!")
print("=" * 60)
