from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base


class Research(Base):
    __tablename__ = "research"

    id = Column(Integer, primary_key=True, autoincrement=True)
    research_link = Column(String(1024), nullable=False)
    vector_link = Column(String(1024), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)

    user = relationship("Users", back_populates="researches")
    visits = relationship("ResearchVisit", back_populates="research")
