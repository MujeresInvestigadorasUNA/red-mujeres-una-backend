from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base

class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_type_id = Column(Integer, ForeignKey("users_types.id", ondelete="SET NULL"), default=1, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(150), nullable=False)
    last_name = Column(String(300), nullable=False)
    password = Column(String(255), nullable=False)
    photo = Column(String(255))

    # Define relationship to UserType
    user_type = relationship("UserType", back_populates="users")

    # Relationship to Forums
    forum = relationship("Forums", back_populates="user", uselist=False)

    # Relationship to Courses
    courses = relationship("Courses", back_populates="user")