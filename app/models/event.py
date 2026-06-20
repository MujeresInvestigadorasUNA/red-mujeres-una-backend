from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.db import Base

class Event(Base):
    __tablename__ = "event"

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
    is_public = Column(Boolean, default=False, nullable=False)

    user = relationship("Users", back_populates="events")
