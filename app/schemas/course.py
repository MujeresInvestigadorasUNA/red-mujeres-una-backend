from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import date, time

# --- Sesiones ---
class CourseSessionCreate(BaseModel):
    date: date
    start_time: time
    end_time: time
    timezone: Optional[str] = Field(None, max_length=50)
    location: Optional[str] = Field(None, max_length=150)

class CourseSessionOut(CourseSessionCreate):
    id: int
    class Config:
        from_attributes = True

# --- Curso ---
class CourseBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=10_000)
    instructor_name: str = Field(..., min_length=2, max_length=150)
    capacity: int = Field(30, ge=1, le=10000)

class CourseCreate(CourseBase):
    # puedes crear el curso y opcionalmente registrar sus sesiones de una vez
    sessions: List[CourseSessionCreate] = []

class CourseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=10_000)
    instructor_name: Optional[str] = Field(None, min_length=2, max_length=150)
    capacity: Optional[int] = Field(None, ge=1, le=10000)
    status: Optional[Literal["draft", "published", "archived"]] = None

class CourseOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    instructor_name: str
    created_by: int
    capacity: int
    status: Literal["draft", "published", "archived"]
    sessions: List[CourseSessionOut] = []
    enrolled_count: int

    class Config:
        from_attributes = True

# --- Inscripciones ---
class EnrollResponse(BaseModel):
    course_id: int
    user_id: int
    waitlisted: bool

class EnrollmentListItem(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: str
