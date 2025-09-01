from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserUpdate, UserOut
from app.services import user_service

def register_user(db: Session, payload: UserCreate) -> UserOut:
    user = user_service.create_user(db, payload)
    return UserOut.model_validate(user)

def update_user_profile(db: Session, user_id: int, payload: UserUpdate) -> UserOut:
    user = user_service.update_user(db, user_id=user_id, data=payload)
    return UserOut.model_validate(user)

def list_all_users(db: Session, skip: int = 0, limit: int = 50) -> list[UserOut]:
    users = user_service.list_users(db, skip=skip, limit=limit)
    return [UserOut.model_validate(u) for u in users]
