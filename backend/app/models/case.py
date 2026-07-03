from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

class Case(Base):
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True, index=True)
    case_ref = Column(String, unique=True, index=True, nullable=False)
    applicant_name = Column(String, index=True, nullable=False)
    property_address = Column(String, nullable=False)
    status = Column(String, default="Pending Review")
    risk_score = Column(Float, default=0.0)
    
    assigned_officer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    assigned_to_user = relationship("User", back_populates="cases")
    documents = relationship("Document", back_populates="case", cascade="all, delete")
    fraud_reports = relationship("FraudReport", back_populates="case", cascade="all, delete")
    notes = relationship("InvestigationNote", back_populates="case", cascade="all, delete")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("Case", back_populates="documents")
    uploader = relationship("User")
