from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.auth import require_token
from app.controllers.user_types_controller import UserTypeController
from app.schemas.user_types import UserTypeBase, UserTypeOut

router = APIRouter(prefix="/user_types", tags=["user_types"])


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("", response_model=list[UserTypeOut])
def get_user_types(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return UserTypeController.get_all(db, skip, limit)


@router.get("/{user_type_id}", response_model=UserTypeOut)
def get_user_type(user_type_id: int, db: Session = Depends(get_db)):
    return UserTypeController.get_by_id(db, user_type_id)


# ── Protected endpoints ───────────────────────────────────────────────────────

@router.post("", response_model=UserTypeOut, status_code=201)
def create_user_type(
    user_type: UserTypeBase,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return UserTypeController.create(db, user_type)
