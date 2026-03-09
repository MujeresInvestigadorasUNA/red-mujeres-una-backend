from sqlalchemy.orm import Session
from app.models.user_types import UserType

class UserTypeRepository:
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(UserType).order_by(UserType.id).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, user_type_id: int):
        return db.query(UserType).filter(UserType.id == user_type_id).first()

    @staticmethod
    def get_by_description(db: Session, description: str):
        # This method checks if a UserType with the same description already exists
        return db.query(UserType).filter(UserType.description == description).first()

    @staticmethod
    def create(db: Session, description: str):
        user_type = UserType(description=description)
        db.add(user_type)
        db.commit()
        db.refresh(user_type)
        return user_type