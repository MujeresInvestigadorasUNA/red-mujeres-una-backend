from sqlalchemy.orm import Session
from app.repositories.user_types_repository import UserTypeRepository
from app.schemas.user_types import UserTypeBase

class UserTypeService:
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100):
        return UserTypeRepository.get_all(db, skip, limit)

    @staticmethod
    def get_by_id(db: Session, user_type_id: int):
        return UserTypeRepository.get_by_id(db, user_type_id)

    @staticmethod
    def create(db: Session, user_type: UserTypeBase):
        # You could add any extra business logic here (e.g., checking if the description is unique)
        existing_type = UserTypeRepository.get_by_description(db, user_type.description)
        if existing_type:
            raise ValueError("User type description already exists")
        return UserTypeRepository.create(db, user_type.description)
