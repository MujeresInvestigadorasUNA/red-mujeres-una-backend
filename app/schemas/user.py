from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name:  str = Field(..., min_length=1, max_length=100)
    email:      EmailStr
    password:   str = Field(..., min_length=8, max_length=128)

class UserOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name:  str | None = Field(None, min_length=1, max_length=100)
