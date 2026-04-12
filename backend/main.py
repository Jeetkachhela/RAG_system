from fastapi import FastAPI, HTTPException, Depends, Request, UploadFile, File, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging
import os
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ingest import parse_and_ingest, parse_and_ingest_from_bytes
from retriever import retrieve_context_with_meta
from chat import generate_chat_stream
from connectivity import get_system_status, set_current_mode, get_current_mode
from analytics import get_all_analytics, log_chat_query

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kanan Conversational RAG API")

@app.get("/")
@app.head("/")
async def read_root():
    return {
        "status": "Kanan RAG Backend is running.", 
        "version": "2.0.0-async",
        "endpoints": ["/api/chat", "/api/ingest", "/api/status", "/api/config/mode", "/api/analytics"]
    }

# Phase 6: Basic in-memory rate limiting (per IP + per user)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_rate_events: dict[str, list[float]] = {}

def _rate_limit_key(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    return ip

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

def rate_limit_dep(request: Request):
    _check_rate_limit(_rate_limit_key(request))
    return True

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Audited Fix: Ensures CORS headers are preserved even on fatal Unhandled Exceptions, preventing opaque Frontend Network Errors."""
    logger.error(f"Global unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if str(exc) else "Internal Server Error"},
        headers={"Access-Control-Allow-Origin": "*"}  # Force CORS reflection
    )

@app.get("/api/health")
async def health_check():
    """Independent heartbeat endpoint for cloud loadbalancers to ping our system without burning token rate limits."""
    return {"status": "healthy", "service": "kanan-rag-engine", "timestamp": time.time()}

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

allow_origins = ["*"]
allow_credentials = False

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
    # Only check Content-Length header to avoid consuming the body stream in middleware
    cl = request.headers.get("content-length")
    if cl:
        try:
            if int(cl) > MAX_BODY_BYTES:
                return StreamingResponse(
                    iter(["Request too large."]), 
                    status_code=413
                )
        except (ValueError, TypeError):
            pass
    return await call_next(request)

import sys

@app.on_event("startup")
async def validate_production_config():
    """Ensure critical environment variables are present before starting."""
    required = ["MONGODB_URI", "GROQ_API_KEY"]
    missing = [env for env in required if not os.getenv(env)]
    if missing:
        msg = f"CRITICAL BOOT FAILURE: Missing required environment variables: {', '.join(missing)}. Halting serverless deployment."
        logger.error(msg)
        sys.exit(1)
    logger.info("Startup validation complete. All required environment configurations are present.")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@app.post("/api/chat")
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    background_tasks: BackgroundTasks,
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
        
        start_time = time.time()
        # Offload synchronous PyMongo lookup bounds to threadpool to prevent ASGI event loop blocking
        context_str, meta = await run_in_threadpool(retrieve_context_with_meta, last_user_query, chat_history=recent_messages)
        latency = time.time() - start_time
        
        # Log usage to analytics asynchronously
        background_tasks.add_task(log_chat_query, last_user_query, latency)

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



@app.post("/api/ingest")
async def ingest_endpoint():
    try:
        logger.info("Starting ingestion process...")
        record_count = parse_and_ingest()
        logger.info(f"Ingestion successful. {record_count} records processed.")
        return {"status": "success", "message": f"Successfully ingested {record_count} records into MongoDB Atlas."}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@app.post("/api/upload")
async def upload_endpoint(file: UploadFile = File(...)):
    """Upload a new Excel file to replace the existing agent data."""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are accepted.")
    try:
        logger.info(f"Received file upload: {file.filename}")
        file_bytes = await file.read()
        record_count = parse_and_ingest_from_bytes(file_bytes, file.filename)
        logger.info(f"Upload ingestion successful. {record_count} records processed.")
        return {"status": "success", "message": f"Successfully replaced data with {record_count} records from '{file.filename}'."}
    except Exception as e:
        logger.error(f"Upload ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

@app.get("/api/status")
async def get_status_endpoint():
    try:
        return get_system_status()
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"mode": "offline", "status": "error", "error": str(e)}



@app.get("/api/analytics")
async def analytics_endpoint():
    try:
        return get_all_analytics()
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {e}")

@app.get("/")
def read_root():
    return {"status": "Kanan RAG Backend is running.", "endpoints": ["/api/chat", "/api/ingest", "/api/status", "/api/config/mode", "/api/analytics"]}
