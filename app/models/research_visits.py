from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.db import Base

class ResearchVisit(Base):
    __tablename__ = "research_visits"
    __table_args__ = (UniqueConstraint("user_id", "research_id", name="uq_research_visit_user_research"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    visited_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = relationship("Users", back_populates="research_visits")
    research = relationship("Research", back_populates="visits")
