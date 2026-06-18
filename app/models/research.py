from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base


class Research(Base):
    __tablename__ = "research"

    id = Column(Integer, primary_key=True, autoincrement=True)
    research_link = Column(String(1024), nullable=False)
    vector_link = Column(String(1024), nullable=True)  # nullable during processing
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    status = Column(String(20), default="processing", nullable=False)  # processing, ready, failed

    user = relationship("Users", back_populates="researches")
    visits = relationship("ResearchVisit", back_populates="research")
    likes = relationship("ResearchLike", back_populates="research")
    like_events = relationship("ResearchLikeEvent", back_populates="research")
    authors = relationship("ResearchAuthor", back_populates="research", cascade="all, delete-orphan")
