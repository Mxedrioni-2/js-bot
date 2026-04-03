import os
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]
HASHING_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("SESSION_EXPIRATION_TIME_MINS", 480))

pwd_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl = "/auth/token")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm = HASHING_ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Invalid or expired token",
        headers = {"WWW-Authenticate": "Bearer"}
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [HASHING_ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "user")
        if username is None:
            raise credentials_exception
        return {"username": username, "role": role}
    except jwt.exceptions.PyJWTError:
        raise credentials_exception
    
def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user
