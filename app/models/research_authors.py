from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.db import Base


class ResearchAuthor(Base):
    __tablename__ = "research_authors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    research_id = Column(Integer, ForeignKey("research.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (UniqueConstraint("research_id", "user_id", name="uq_research_author"),)

    research = relationship("Research", back_populates="authors")
    user = relationship("Users", back_populates="research_authorships")
