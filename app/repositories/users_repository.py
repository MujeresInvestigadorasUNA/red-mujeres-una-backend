from sqlalchemy.orm import Session
from app.models.users import Users
from app.schemas.users import UserCreate

class UsersRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Users).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, user_id: int):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        return user

    @staticmethod
    def get_by_email(db: Session, email: str):
        return db.query(Users).filter(Users.email == email).first()

    @staticmethod
    def create(db: Session, payload: UserCreate):
        user = Users(
            email=payload.email, 
            first_name=payload.first_name, 
            last_name=payload.last_name, 
            password=payload.password, 
            user_type_id=payload.user_type_id
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def update(db: Session, user_id: int, email: str, first_name: str, last_name: str, password: str, photo: str):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.email = email or user.email
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.password = password or user.password
        user.photo = photo
        
        db.commit()
        db.refresh(user)
        return True

    @staticmethod
    def delete(db: Session, user_id: int):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            return False
        db.delete(user)
        db.commit()
        return True