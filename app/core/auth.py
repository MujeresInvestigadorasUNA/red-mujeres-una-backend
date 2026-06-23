import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from sqlalchemy.orm import Session
from app.core.db import get_db

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Validate a Firebase ID Token from the Authorization header."""
    from app.core.firebase import ensure_initialized

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    ensure_initialized()
    try:
        decoded = firebase_auth.verify_id_token(credentials.credentials)
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    email = decoded.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not contain an email",
        )

    return {"sub": email, "uid": decoded["uid"], "email_verified": decoded.get("email_verified", False)}


def require_admin(
    payload: dict = Depends(require_token),
    db: Session = Depends(get_db),
) -> dict:
    from app.repositories.users_repository import UsersRepository

    email = payload.get("sub", "")
    user = UsersRepository.get_by_email(db, email)
    if not user or user.user_type_id != 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return payload


def require_researcher_or_admin(
    payload: dict = Depends(require_token),
    db: Session = Depends(get_db),
) -> dict:
    from app.repositories.users_repository import UsersRepository

    email = payload.get("sub", "")
    user = UsersRepository.get_by_email(db, email)
    if not user or user.user_type_id not in (2, 3):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Researcher or admin privileges required",
        )
    return payload
