from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ingest import parse_and_ingest
from retriever import retrieve_context_with_meta
from chat import generate_chat_stream
from connectivity import get_system_status, set_current_mode, is_ollama_available
from analytics import get_all_analytics
from auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
    authenticate_user,
    create_access_token_for_user,
    create_user,
    ensure_first_admin_if_empty,
    get_current_user,
    get_current_user_optional,
    require_role,
    request_password_reset,
    reset_password_with_token,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kanan Conversational RAG API")

# Phase 6: Basic in-memory rate limiting (per IP + per user)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_rate_events: dict[str, list[float]] = {}

def _rate_limit_key(request: Request, user: UserOut | None) -> str:
    ip = request.client.host if request.client else "unknown"
    email = (user.email if user else "anon")
    return f"{ip}:{email}"

def _check_rate_limit(key: str):
    now = time.time()
    window_start = now - 60.0
    events = _rate_events.get(key, [])
    events = [t for t in events if t >= window_start]
    if len(events) >= RATE_LIMIT_PER_MINUTE:
        _rate_events[key] = events
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    events.append(now)
    _rate_events[key] = events

def rate_limit_dep(request: Request, user: UserOut = Depends(get_current_user)):
    _check_rate_limit(_rate_limit_key(request, user))
    return True

# Phase 6: Basic request size limits
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", "200000"))
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "12"))
MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "4000"))

# Setup CORS for the frontend
def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins

cors_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS"))
allow_origins = cors_origins if cors_origins else ["http://localhost:5173", "http://127.0.0.1:5173", "https://rag-system-7fca.vercel.app"]
allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Kanan-Warnings", "X-Kanan-Mode", "X-Kanan-Sources"],
)

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    # Avoid reading streaming responses; only limit incoming request bodies.
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Request too large.")
        except Exception:
            pass
    body = await request.body()
    if body and len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Request too large.")
    return await call_next(request)

@app.on_event("startup")
def validate_production_config():
    env = os.getenv("ENV", "development").lower()
    if env == "production" and not os.getenv("JWT_SECRET"):
        raise RuntimeError("JWT_SECRET must be set in production.")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@app.post("/api/chat")
def chat_endpoint(
    req: ChatRequest,
    request: Request,
    user: UserOut = Depends(get_current_user),
    _rl: bool = Depends(rate_limit_dep),
):
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages array cannot be empty")
    if len(req.messages) > MAX_MESSAGES:
        raise HTTPException(status_code=400, detail=f"Too many messages. Max allowed is {MAX_MESSAGES}.")
    for m in req.messages:
        if m.content and len(m.content) > MAX_MESSAGE_CHARS:
            raise HTTPException(status_code=400, detail=f"Message too long. Max chars is {MAX_MESSAGE_CHARS}.")

    # Find the last user message for RAG search
    last_user_query = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            last_user_query = msg.content
            break

    if not last_user_query:
        raise HTTPException(status_code=400, detail="No user message found.")

    # Convert messages to raw dicts for the retriever and chat module
    raw_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    logger.info(f"[RAG] Query: {last_user_query}")
    try:
        # Keep only the last 6 messages to prevent LLM context bloat and hallucinations
        recent_messages = raw_messages[-6:] if len(raw_messages) > 6 else raw_messages
        context_str, meta = retrieve_context_with_meta(last_user_query, chat_history=recent_messages)

        headers = {}
        if meta.get("warnings"):
            headers["X-Kanan-Warnings"] = " | ".join(meta["warnings"])[:1000]
        if meta.get("mode"):
            headers["X-Kanan-Mode"] = str(meta["mode"])
        if meta.get("sources") is not None:
            headers["X-Kanan-Sources"] = ",".join(meta.get("sources") or [])

        return StreamingResponse(
            generate_chat_stream(messages=recent_messages, retrieved_context=context_str),
            media_type="text/event-stream",
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error during chat generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/register", response_model=UserOut)
def register_endpoint(req: RegisterRequest, current_user: UserOut | None = Depends(get_current_user_optional)):
    # First ever registered user becomes admin (bootstrap).
    roles = ensure_first_admin_if_empty(req.email)
    if roles != ["admin"]:
        # After bootstrap, only admins can create users.
        if not current_user or "admin" not in (current_user.roles or []):
            raise HTTPException(status_code=403, detail="Registration is restricted. Ask an admin to create your account.")
        roles = ["user"]
    return create_user(req.email, req.password, roles=roles)

@app.post("/api/auth/login", response_model=TokenResponse)
def login_endpoint(req: LoginRequest, request: Request):
    _check_rate_limit(_rate_limit_key(request, None))
    user = authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token_for_user(user["email"], user.get("roles") or ["user"])
    return TokenResponse(access_token=token)

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@app.post("/api/auth/forgot-password")
def forgot_password_endpoint(req: ForgotPasswordRequest, request: Request):
    _check_rate_limit(_rate_limit_key(request, None))
    token = request_password_reset(req.email)
    if token:
        # WARNING: Logging the token directly to the console for testing since SMTP is not configured.
        logger.warning(f"\n{'='*50}\n[DEV TESTING] PASSWORD RESET REQUESTED\nEmail: {req.email}\nToken: {token}\n{'='*50}\n")
    return {"status": "success", "message": "If the email is registered, a password reset link has been sent."}

@app.post("/api/auth/reset-password")
def reset_password_endpoint(req: ResetPasswordRequest):
    success = reset_password_with_token(req.token, req.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")
    return {"status": "success", "message": "Password successfully reset."}

@app.get("/api/auth/me", response_model=UserOut)
def me_endpoint(user: UserOut = Depends(get_current_user)):
    return user

@app.post("/api/ingest")
def ingest_endpoint(user: UserOut = Depends(require_role("admin"))):
    try:
        logger.info("Starting ingestion process...")
        record_count = parse_and_ingest()
        logger.info(f"Ingestion successful. {record_count} records processed.")
        return {"status": "success", "message": f"Successfully ingested {record_count} records into MongoDB Atlas."}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@app.get("/api/status")
def get_status_endpoint():
    try:
        return get_system_status()
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"mode": "offline", "status": "error", "error": str(e)}

@app.post("/api/config/mode")
def set_mode_endpoint(req: dict, user: UserOut = Depends(require_role("admin"))):
    mode = req.get("mode")
    if mode not in ["online", "offline"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Choose 'online' or 'offline'.")
    set_current_mode(mode)
    return {"status": "success", "mode": mode}

@app.get("/api/analytics")
def analytics_endpoint(user: UserOut = Depends(get_current_user)):
    try:
        return get_all_analytics()
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {e}")

@app.get("/")
def read_root():
    return {"status": "Kanan RAG Backend is running.", "endpoints": ["/api/chat", "/api/ingest", "/api/status", "/api/config/mode", "/api/analytics"]}
