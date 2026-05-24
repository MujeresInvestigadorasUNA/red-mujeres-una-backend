from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    photo: Optional[str] = None
    user_profession: Optional[str] = None
    user_description: Optional[str] = None
    is_public: Optional[bool] = False

class UserCreate(UserBase):
    email: EmailStr
    password: str  # We will hash this password later
    user_type_id: int

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    photo: Optional[str] = None
    user_profession: Optional[str] = None
    user_description: Optional[str] = None
    is_public: Optional[bool] = None
    user_type_id: Optional[int] = None

class UserUpdateResponse(BaseModel):
    success: bool

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserLoginResponse(UserBase):
    id: int
    user_type_id: int
    access_token: str

class UserOut(BaseModel):
    id: int
    access_token: str

    class Config:
        from_attributes = True

class UsersDetailsOut(UserBase):
    id: int
    user_type_id: int

    class Config:
        from_attributes = True


class ProfilePictureUrlOut(BaseModel):
    url: str
    expires_at: datetime