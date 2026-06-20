from datetime import date
from pydantic import BaseModel
from typing import Optional
from app.schemas.users import UserBase


class EventBase(BaseModel):
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
    is_public: bool = False


class EventByUserBase(BaseModel):
    id: int
    title: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    modality: Optional[str] = None
    max_registration_date: Optional[date] = None
    initial_date: Optional[date] = None
    final_date: Optional[date] = None
    is_public: bool = False


class EventCreate(BaseModel):
    user_id: int


class EventCreateResponse(BaseModel):
    id: int


class EventUpdate(BaseModel):
    title: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    modality: Optional[str] = None
    max_registration_date: Optional[date] = None
    initial_date: Optional[date] = None
    final_date: Optional[date] = None
    is_public: bool = False


class EventUpdateResponse(BaseModel):
    success: bool


class EventOut(EventBase):
    id: int
    taught_by: Optional[str] = None

    class Config:
        from_attributes = True
