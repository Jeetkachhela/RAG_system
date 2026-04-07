import os
from datetime import datetime, timedelta
from typing import Optional, Any
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
import bcrypt
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
import secrets

load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "kanan_rag")
USERS_COLLECTION = "users"

oauth2_scheme_required = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

class TokenData(BaseModel):
    email: Optional[str] = None
    roles: list[str] = []

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    email: str
    roles: list[str]
    disabled: bool = False
    created_at: Optional[datetime] = None

def verify_password(plain_password, hashed_password):
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

_mongo_client: MongoClient | None = None

def get_auth_db():
    global _mongo_client
    if not MONGODB_URI:
        raise HTTPException(status_code=500, detail="MONGODB_URI is not configured.")
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = _mongo_client[DB_NAME]
    db[USERS_COLLECTION].create_index([("email", ASCENDING)], unique=True)
    return db

def get_users_collection():
    return get_auth_db()[USERS_COLLECTION]

def _normalize_email(email: str) -> str:
    return email.strip().lower()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured.")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token_for_user(email: str, roles: list[str]) -> str:
    expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data={"sub": email, "roles": roles},
        expires_delta=expires,
    )

def get_user_by_email(email: str) -> Optional[dict[str, Any]]:
    col = get_users_collection()
    return col.find_one({"email": _normalize_email(email)})

def ensure_first_admin_if_empty(email: str) -> list[str]:
    col = get_users_collection()
    if col.estimated_document_count() == 0:
        return ["admin"]
    return ["user"]

def create_user(email: str, password: str, roles: list[str]) -> UserOut:
    col = get_users_collection()
    now = datetime.utcnow()
    doc = {
        "email": _normalize_email(email),
        "password_hash": get_password_hash(password),
        "roles": roles,
        "disabled": False,
        "created_at": now,
    }
    try:
        col.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=400, detail="User already exists.")
    return UserOut(email=doc["email"], roles=doc["roles"], disabled=doc["disabled"], created_at=doc["created_at"])

def authenticate_user(email: str, password: str) -> Optional[dict[str, Any]]:
    user = get_user_by_email(email)
    if not user:
        return None
    if user.get("disabled"):
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None
    return user

async def get_current_user_email(token: str = Depends(oauth2_scheme_required)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return _normalize_email(email)
    except JWTError:
        raise credentials_exception

async def get_current_user(token: str = Depends(oauth2_scheme_required)) -> UserOut:
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured.")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        roles = payload.get("roles") or []
        if not email:
            raise credentials_exception
        user = get_user_by_email(email)
        if not user or user.get("disabled"):
            raise credentials_exception
        return UserOut(
            email=_normalize_email(user["email"]),
            roles=list(roles),
            disabled=bool(user.get("disabled", False)),
            created_at=user.get("created_at"),
        )
    except JWTError:
        raise credentials_exception

async def get_current_user_optional(token: str | None = Depends(oauth2_scheme_optional)) -> UserOut | None:
    if not token:
        return None
    try:
        return await get_current_user(token=token)  # type: ignore[arg-type]
    except HTTPException:
        return None

def require_role(required: str):
    async def _dep(user: UserOut = Depends(get_current_user)) -> UserOut:
        if required not in (user.roles or []):
            raise HTTPException(status_code=403, detail="Insufficient permissions.")
        return user
    return _dep

def request_password_reset(email: str) -> Optional[str]:
    """Generates a reset token if the user exists, returns the token (or None if not found)."""
    col = get_users_collection()
    user = get_user_by_email(email)
    if not user:
        return None
    
    reset_token = secrets.token_urlsafe(32)
    # Valid for 15 minutes
    expiry = datetime.utcnow() + timedelta(minutes=15)
    
    col.update_one(
        {"_id": user["_id"]},
        {"$set": {"reset_token": reset_token, "reset_token_expiry": expiry}}
    )
    return reset_token

def reset_password_with_token(token: str, new_password: str) -> bool:
    """Validates the reset token and updates the password. Returns True if successful."""
    col = get_users_collection()
    user = col.find_one({
        "reset_token": token,
        "reset_token_expiry": {"$gt": datetime.utcnow()}
    })
    
    if not user:
        return False
        
    hashed_password = get_password_hash(new_password)
    col.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hashed_password},
            "$unset": {"reset_token": "", "reset_token_expiry": ""}
        }
    )
    return True
