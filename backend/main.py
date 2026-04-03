from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import logging

from ingest import parse_and_ingest
from retriever import retrieve_context
from chat import generate_chat_stream

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kanan Conversational RAG API")

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="Messages array cannot be empty")

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
        context_str = retrieve_context(last_user_query, chat_history=recent_messages)

        return StreamingResponse(
            generate_chat_stream(messages=recent_messages, retrieved_context=context_str),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error during chat generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ingest")
def ingest_endpoint():
    try:
        logger.info("Starting ingestion process...")
        record_count = parse_and_ingest()
        logger.info(f"Ingestion successful. {record_count} records processed.")
        return {"status": "success", "message": f"Successfully ingested {record_count} records into ChromaDB."}
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

@app.get("/")
def read_root():
    return {"status": "Kanan RAG Backend is running.", "endpoints": ["/api/chat", "/api/ingest"]}
