from pydantic import BaseModel

class UserTypeBase(BaseModel):
    description: str

class UserTypeOut(UserTypeBase):
    id: int

    class Config:
        from_attributes = True  # This allows us to convert SQLAlchemy models to Pydantic models
