from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Annotated
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.user import UserOut, UserUpdate
from app.controllers.user_controller import list_all_users, update_user_profile

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserOut)
def get_me(current_user = Depends(get_current_user)):
    return UserOut.model_validate(current_user)

@router.get("/", response_model=list[UserOut])
def list_users(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _: Annotated[dict, Depends(get_current_user)] = None,
):
    return list_all_users(db, skip=skip, limit=limit)

@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return update_user_profile(db, user_id=current_user.id, payload=payload)
