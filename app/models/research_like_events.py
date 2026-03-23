from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.db import Base


class ResearchLikeEvent(Base):
    __tablename__ = "research_like_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    action = Column(String(10), nullable=False, index=True)  # like | unlike
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    user = relationship("Users", back_populates="research_like_events")
    research = relationship("Research", back_populates="like_events")
