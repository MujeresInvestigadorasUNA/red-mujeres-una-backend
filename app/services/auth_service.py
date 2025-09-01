from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.security import verify_password, create_access_token
from app.services.user_service import get_user_by_email

def authenticate(db: Session, *, email: str, password: str) -> str:
    user = get_user_by_email(db, email=email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return create_access_token(subject=user.email)
