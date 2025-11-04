from datetime import datetime, timedelta
import jwt
from app.core.config import settings

# Secret key for encoding and decoding JWTs
SECRET_KEY = settings.DB_PASSWORD  # You can store this in your .env file
ALGORITHM = "HS256"  # JWT algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Set the expiration time

# Function to create JWT access token
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt