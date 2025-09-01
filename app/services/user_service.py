from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password

def get_user_by_email(db: Session, *, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()

def get_user_by_id(db: Session, *, user_id: int) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()

def create_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, email=data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=data.email.lower(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, *, user_id: int, data: UserUpdate) -> User:
    user = get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if data.first_name is not None:
        user.first_name = data.first_name.strip()
    if data.last_name is not None:
        user.last_name = data.last_name.strip()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def list_users(db: Session, *, skip: int = 0, limit: int = 50) -> list[User]:
    stmt = select(User).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())
