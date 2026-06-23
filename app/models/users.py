from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # SQL Server doesn't allow ON DELETE SET NULL when the column is NOT NULL.
    # Use NO ACTION for SQL Server compatibility (do not change user_type on delete),
    # and keep the column non-nullable with a default value.
    user_type_id = Column(Integer, ForeignKey("users_types.id", ondelete="NO ACTION"), default=1, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(150), nullable=False)
    last_name = Column(String(300), nullable=False)
    photo = Column(String(255))
    user_profession = Column(String(255), nullable=True)
    user_description = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)

    # Define relationship to UserType
    user_type = relationship("UserType", back_populates="users")

    # Relationship to Events
    events = relationship("Event", back_populates="user")

    # Relationship to Research
    researches = relationship("Research", back_populates="user")
    research_visits = relationship("ResearchVisit", back_populates="user")
    research_likes = relationship("ResearchLike", back_populates="user")
    research_like_events = relationship("ResearchLikeEvent", back_populates="user")
    research_authorships = relationship("ResearchAuthor", back_populates="user")