from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.controllers.users_controller import UserController
from app.schemas.users import UserCreate, UserUpdate, UserOut, UsersDetailsOut, UserLogin, UserLoginResponse, UserUpdateResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=list[UsersDetailsOut])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return UserController.list_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=UsersDetailsOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return UserController.get_user(db, user_id)

@router.post("/", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return UserController.create_user(db, payload)

@router.put("/{user_id}", response_model=UserUpdateResponse)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    return UserController.update_user(db, user_id, payload)

@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    return UserController.delete_user(db, user_id)

@router.post("/login", response_model=UserLoginResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    return UserController.login(db, user)