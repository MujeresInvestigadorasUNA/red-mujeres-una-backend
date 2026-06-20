from sqlalchemy.orm import Session
from app.models.users import Users
from app.schemas.users import UserCreate

class UsersRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int | None = None):
        query = db.query(Users).order_by(Users.id).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

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
            user_type_id=payload.user_type_id,
            user_profession=payload.user_profession,
            user_description=payload.user_description,
            is_public=payload.is_public if payload.is_public is not None else False
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def update(db: Session, user_id: int, email: str, first_name: str, last_name: str, password: str, photo: str, user_profession: str = None, user_description: str = None, is_public: bool = None):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.email = email or user.email
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.password = password or user.password

        if user_profession is not None:
            user.user_profession = user_profession
        if user_description is not None:
            user.user_description = user_description
        if is_public is not None:
            user.is_public = is_public

        db.commit()
        db.refresh(user)
        return True

    @staticmethod
    def update_user_type(db: Session, user_id: int, user_type_id: int):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        user.user_type_id = user_type_id
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete(db: Session, user_id: int):
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            return False
        db.delete(user)
        db.commit()
        return True

    @staticmethod
    def get_researchers(db: Session, is_public_only: bool = False, skip: int = 0, limit: int | None = None):
        """Get researchers (user_type_id = 2). Optionally filter by is_public = True."""
        query = db.query(Users).filter(Users.user_type_id.in_([2, 3]))

        if is_public_only:
            query = query.filter(Users.is_public == True)

        query = query.order_by(Users.id).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        return query.all()