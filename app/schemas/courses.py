from datetime import date
from pydantic import BaseModel
from typing import Optional
from app.schemas.users import UserBase

class CourseBase(BaseModel):
    id: int
    user: UserBase
    user_id: int 
    title: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    modality: Optional[str] = None
    max_registration_date: Optional[date] = None
    initial_date: Optional[date] = None
    final_date: Optional[date] = None
    max_quotas: Optional[int] = None
    is_public: bool = False

class CourseByUserBase(BaseModel):
    id: int
    title: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    modality: Optional[str] = None
    max_registration_date: Optional[date] = None
    initial_date: Optional[date] = None
    final_date: Optional[date] = None
    max_quotas: Optional[int] = None
    is_public: bool = False

class CourseCreate(BaseModel):
    user_id: int

class CourseCreateResponse(BaseModel):
    id: int

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    modality: Optional[str] = None
    max_registration_date: Optional[date] = None
    initial_date: Optional[date] = None
    final_date: Optional[date] = None
    max_quotas: Optional[int] = None
    is_public: bool = False

class CourseUpdateResponse(BaseModel):
    success: bool

class CourseOut(CourseBase):
    id: int
    taught_by: Optional[str] = None

    class Config:
        from_attributes = True