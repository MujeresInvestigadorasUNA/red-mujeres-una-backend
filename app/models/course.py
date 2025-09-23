from sqlalchemy import (
    Column, Integer, String, Text, Date, Time, DateTime,
    ForeignKey, UniqueConstraint, Enum, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base  # misma Base que User

class CourseStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Quien IMPARTE el curso (texto libre)
    instructor_name = Column(String(150), nullable=False)

    # Quien CREÓ el curso (usuario existente)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    capacity = Column(Integer, nullable=False, default=30)
    status = Column(Enum(CourseStatus), nullable=False, default=CourseStatus.published)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    creator = relationship("User", lazy="joined")
    sessions = relationship("CourseSession", cascade="all, delete-orphan", back_populates="course", lazy="selectin")
    enrollments = relationship("CourseEnrollment", cascade="all, delete-orphan", back_populates="course", lazy="selectin")

class CourseSession(Base):
    __tablename__ = "course_sessions"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)

    # Soporta múltiples días/horas para el mismo curso
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # Campos opcionales
    timezone = Column(String(50), nullable=True)       # e.g. "America/Costa_Rica"
    location = Column(String(150), nullable=True)      # aula/sala/zoom link

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="sessions")

    __table_args__ = (
        # Evita duplicar exactamente la misma franja para el mismo curso
        UniqueConstraint("course_id", "date", "start_time", "end_time", name="uq_course_timeslot"),
    )

class CourseEnrollment(Base):
    __tablename__ = "course_enrollments"

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Por si luego manejas asistencia por sesión
    waitlisted = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    course = relationship("Course", back_populates="enrollments")
    user = relationship("User", lazy="joined")

    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_user_unique"),
    )
