from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class AILog(Base):
    __tablename__ = "ai_logs"
    __table_args__ = {'extend_existing': True}

    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    model = Column(String(50))
    feature_name = Column(String(100), default="Samhita RAG")
    prompt = Column(Text)
    response = Column(Text)
    tokens_used = Column(Integer, default=0)
    cost = Column(Integer, default=0)
    feedback_status = Column(String(30), default="accepted")
    feedback_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())