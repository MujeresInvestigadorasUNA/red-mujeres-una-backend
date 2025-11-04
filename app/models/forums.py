from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base

class Forums(Base):
    __tablename__ = "forums"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    user_profession = Column(String(255), nullable=True)
    user_description = Column(String(500), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)

    # Define relationship to Users
    user = relationship("Users", back_populates="forum")