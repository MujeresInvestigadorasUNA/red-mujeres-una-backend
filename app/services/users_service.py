from sqlalchemy.orm import Session
from app.repositories.users_repository import UsersRepository
from app.repositories.forums_repository import ForumsRepository
from app.schemas.users import UserCreate, UserUpdate
from app.models.users import Users
from datetime import timedelta
from app.core.auth import create_access_token

class UsersService:
    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int = 50) -> list[Users]:
        return UsersRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_user(db: Session, user_id: int) -> Users | None:
        user = UsersRepository.get_by_id(db, user_id)

        if user.user_type_id == 2:
            forum = ForumsRepository.get_by_user_id(db, user_id)
            if forum:
                user.profession = forum.user_profession

        return user
    
    @staticmethod
    def get_by_email(db: Session, email: str) -> Users | None:
        return UsersRepository.get_by_email(db, email)

    @staticmethod
    def create_user(db: Session, payload: UserCreate) -> dict:
        # Business rule example: unique email
        existing = UsersRepository.get_by_email(db, payload.email)
        if existing:
            raise ValueError("Email already registered")
    
        user = UsersRepository.create(db, payload)

        # Persist the user to ensure the generated id is available
        db.commit()
        db.refresh(user)

        if payload.user_type_id == 2:
            ForumsRepository.create(
                db,
                user_id=user.id,
                user_profession=None,
                user_description=None
            )

        # Create the JWT token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        return { "id": user.id, "access_token": access_token }

    @staticmethod
    def update_user(db: Session, user_id: int, payload: UserUpdate) -> Users | None:

        # If email change is requested, check uniqueness
        if payload.email:
            other = UsersRepository.get_by_email(db, payload.email)
            if other and other.id != user_id:
                raise ValueError("Email already registered to another user")
            
        print(payload.user_type_id, payload.profession)
        if payload.user_type_id == 2 and payload.profession:
            print('asasdd')
            ForumsRepository.update(
                db,
                forum_id=user_id,
                user_profession=payload.profession,
                user_description=None,
                is_public=None
            )

        return UsersRepository.update(
            db,
            user_id,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password=payload.password,
            photo=payload.photo
        )

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        user = UsersRepository.get_by_id(db, user_id)
        if not user:
            return False
        UsersRepository.delete(db, user)
        return True

    @staticmethod
    def login(db: Session, user_login) -> dict:
        # Check if the user exists
        user = UsersService.get_by_email(db, user_login.email)
        if user is None or user.password != user_login.password:
            raise ValueError("Invalid credentials")

        # Create the JWT token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        # Return user and token
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_type_id": user.user_type_id,
            "access_token": access_token,
        }