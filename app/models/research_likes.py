from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.db import Base


class ResearchLike(Base):
    __tablename__ = "research_likes"
    __table_args__ = (UniqueConstraint("user_id", "research_id", name="uq_research_like_user_research"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    research_id = Column(Integer, ForeignKey("research.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    liked_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("Users", back_populates="research_likes")
    research = relationship("Research", back_populates="likes")
