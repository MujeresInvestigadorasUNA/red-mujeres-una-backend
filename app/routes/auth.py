from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.auth import Token, LoginIn
from app.schemas.user import UserCreate, UserOut
from app.controllers.auth_controller import login_and_get_token
from app.controllers.user_controller import register_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    return register_user(db, payload)

@router.post("/login", response_model=Token)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    token = login_and_get_token(db, email=payload.email, password=payload.password)
    return {"access_token": token, "token_type": "bearer"}
