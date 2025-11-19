from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.db import Base

class Courses(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
    )

    title = Column(String(150), nullable=True)
    photo = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)
    modality = Column(String(200), nullable=True)
    max_registration_date = Column(Date, nullable=True)
    initial_date = Column(Date, nullable=True)
    final_date = Column(Date, nullable=True)
    max_quotas = Column(Integer, nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)

    user = relationship("Users", back_populates="courses")