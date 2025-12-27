from datetime import datetime, timedelta
import jwt
from app.core.config import settings

# Use names defined in Settings
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALG
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT using the project's settings.

    - Uses `settings.JWT_SECRET` as the key
    - Uses `settings.JWT_ALG` as the algorithm
    - Uses `settings.ACCESS_TOKEN_EXPIRE_MINUTES` when expires_delta is not provided
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.utcnow() + expires_delta
    to_encode = data.copy()
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt