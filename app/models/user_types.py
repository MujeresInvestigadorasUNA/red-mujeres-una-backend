from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.db import Base

class UserType(Base):
    __tablename__ = "users_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(50), unique=True, nullable=False)
    
    # Define relationship to Users
    users = relationship("Users", back_populates="user_type", cascade="all, delete-orphan")