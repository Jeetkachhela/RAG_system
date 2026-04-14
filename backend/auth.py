from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt
from datetime import datetime, timedelta
import os
import logging
from pymongo import MongoClient

router = APIRouter()
logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-kanan-ops-key-2026")
JWT_ALGORITHM = "HS256"

# Connect to DB
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "kanan_rag")

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    users_col = db["kanan_users"]
except Exception as e:
    logger.error(f"Auth DB Error: {e}")
    users_col = None

# Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    security_question: str
    security_answer: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordInit(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    security_answer: str
    new_password: str

# Helpers
def get_password_hash(password: str) -> str:
    # Truncate to 72 characters to prevent bcrypt ValueError for overly long passwords/answers
    return pwd_context.hash(password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password[:72], hashed_password)


def create_access_token(data: dict, expires_delta: timedelta = timedelta(days=7)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/register")
async def register_user(req: RegisterRequest):
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database not connected.")
    
    existing_user = users_col.find_one({"email": req.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_pw = get_password_hash(req.password)
    # We hash the security answer as well so it cannot be extracted if db is breached.
    answer_hash = get_password_hash(req.security_answer.strip().lower())

    user_doc = {
        "email": req.email.lower(),
        "password_hash": hashed_pw,
        "security_question": req.security_question,
        "security_answer_hash": answer_hash,
        "created_at": datetime.utcnow()
    }
    users_col.insert_one(user_doc)
    
    # Auto-login after registration
    token = create_access_token({"sub": req.email.lower()})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login")
async def login_user(req: LoginRequest):
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database error.")
    
    user = users_col.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
        
    token = create_access_token({"sub": user["email"]})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/forgot-password-step1")
async def verify_email_and_get_question(req: ForgotPasswordInit):
    """Checks if email exists and returns the user's security question."""
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database error.")
        
    user = users_col.find_one({"email": req.email.lower()})
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")
        
    return {"security_question": user.get("security_question", "What is your registration code?")}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    if users_col is None:
        raise HTTPException(status_code=500, detail="Database error.")
        
    user = users_col.find_one({"email": req.email.lower()})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Verify the security answer
    answer_valid = verify_password(req.security_answer.strip().lower(), user.get("security_answer_hash", ""))
    if not answer_valid:
        raise HTTPException(status_code=403, detail="Incorrect security answer! Cannot reset password.")
        
    # Update Password
    new_hashed_pw = get_password_hash(req.new_password)
    users_col.update_one({"email": user["email"]}, {"$set": {"password_hash": new_hashed_pw}})
    
    return {"detail": "Password successfully reset!"}
