from sqlalchemy.orm import Session
from app.services.auth_service import authenticate

def login_and_get_token(db: Session, email: str, password: str) -> str:
    return authenticate(db, email=email, password=password)
