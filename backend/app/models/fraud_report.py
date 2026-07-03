from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

class FraudReport(Base):
    __tablename__ = "fraud_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    risk_score = Column(Float, nullable=False)
    fraud_category = Column(String, nullable=False)
    findings = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    ml_result = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    case = relationship("Case", back_populates="fraud_reports")
