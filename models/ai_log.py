# models/ai_log.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class AILog(Base):
    __tablename__ = "ai_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    model = Column(String(50))
    prompt = Column(Text)
    response = Column(Text)
    tokens_used = Column(Integer, default=0)
    cost = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())