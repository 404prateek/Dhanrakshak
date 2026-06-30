import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.session import SessionLocal, engine
from app.database.base import Base
from app.models.user import Role
from app.models import __init__  # register all models

def seed_roles():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        roles = [
            Role(id=1, name="Admin", description="System Administrator"),
            Role(id=2, name="Underwriter", description="Case Underwriter"),
            Role(id=3, name="Auditor", description="Audit Team"),
            Role(id=4, name="Compliance Manager", description="Compliance Manager"),
        ]
        for role in roles:
            existing = db.query(Role).filter(Role.id == role.id).first()
            if not existing:
                db.add(role)
        db.commit()
        print("Roles seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding roles: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_roles()
