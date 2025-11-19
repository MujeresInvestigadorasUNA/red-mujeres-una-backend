from pydantic import BaseModel
from typing import Optional
from app.schemas.users import UserBase

class ForumBase(BaseModel):
    user: UserBase
    user_id: int
    user_profession: str
    user_description: str
    is_public: bool

class ForumCreate(ForumBase):
    user_id: int
    user_profession: Optional[str] = None
    user_description: Optional[str] = None

class ForumUpdate(BaseModel):
    user_profession: Optional[str] = None
    user_description: Optional[str] = None
    photo: Optional[str] = None
    is_public: Optional[bool] = None

class ForumUpdateResponse(BaseModel):
    success: bool

class ForumCreateResponse(BaseModel):
    success: bool

class ForumDetailsOut(ForumBase):
    user_id: int
    user_profession: Optional[str] = None
    user_description: Optional[str] = None
    is_public: Optional[bool] = None 

    class Config:
        from_attributes = True