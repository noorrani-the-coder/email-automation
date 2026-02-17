import os
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional, Dict, Any

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(user_id: int, email: str) -> str:
    """Create a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(tz=timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def extract_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Extract user info from a JWT token."""
    payload = decode_jwt_token(token)
    if payload:
        return {"user_id": payload.get("user_id"), "email": payload.get("email")}
    return None
