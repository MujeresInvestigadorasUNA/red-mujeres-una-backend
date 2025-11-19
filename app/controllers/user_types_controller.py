from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.services.user_types_service import UserTypeService
from app.schemas.user_types import UserTypeOut, UserTypeBase

class UserTypeController:
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100):
        return UserTypeService.get_all(db, skip, limit)

    @staticmethod
    def get_by_id(db: Session, user_type_id: int):
        user_type = UserTypeService.get_by_id(db, user_type_id)
        if not user_type:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User type not found")
        return user_type

    @staticmethod
    def create(db: Session, user_type: UserTypeBase):
        return UserTypeService.create(db, user_type)