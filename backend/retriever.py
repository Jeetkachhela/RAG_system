import os
import re
import json
import logging
import time
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from groq import Groq
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from knowledge_base import get_kb_context
from connectivity import get_current_mode

logger = logging.getLogger(__name__)

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "kanan_rag")
COLLECTION_NAME = "kanan_agents"
WEB_FALLBACK_ENABLED = os.getenv("WEB_FALLBACK_ENABLED", "true").lower() == "true"
WEB_MAX_RESULTS = int(os.getenv("WEB_MAX_RESULTS", "5"))
WEB_MAX_CHARS = int(os.getenv("WEB_MAX_CHARS", "4000"))
REWRITE_CACHE_TTL_SECONDS = int(os.getenv("REWRITE_CACHE_TTL_SECONDS", "300"))
EMBED_CACHE_TTL_SECONDS = int(os.getenv("EMBED_CACHE_TTL_SECONDS", "600"))

client = None
embedder = None
_vector_index_available: bool | None = None
_rewrite_cache: dict[str, tuple[float, tuple[str, str, dict]]] = {}
_embed_cache: dict[str, tuple[float, list[float]]] = {}

# Session for HF API with retries
_hf_session = requests.Session()
_retries = Retry(total=3, backoff_factor=0.2, status_forcelist=[500, 502, 503, 504])
_hf_session.mount("https://", HTTPAdapter(max_retries=_retries))

def _cache_get(cache: dict, key: str, ttl_s: int):
    item = cache.get(key)
    if not item:
        return None
    ts, val = item
    if (time.time() - ts) > ttl_s:
        cache.pop(key, None)
        return None
    return val

def _cache_set(cache: dict, key: str, val):
    cache[key] = (time.time(), val)

def _cache_prune(cache: dict, ttl_s: int, max_size: int = 2048):
    if len(cache) <= max_size:
        return
    now = time.time()
    # Drop expired first
    expired = [k for k, (ts, _) in cache.items() if (now - ts) > ttl_s]
    for k in expired[: max_size // 2]:
        cache.pop(k, None)
    # If still big, drop oldest
    if len(cache) > max_size:
        oldest = sorted(cache.items(), key=lambda kv: kv[1][0])[: max_size // 2]
        for k, _ in oldest:
            cache.pop(k, None)

def _normalize_filter_value(key: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if key == "zone":
        return v.upper()
    if key == "active":
        vv = v.lower()
        if vv in {"yes", "y", "true", "1"}:
            return "Yes"
        if vv in {"no", "n", "false", "0"}:
            return "No"
        return v.title()
    if key in {"rank", "city", "state", "category", "bdm", "team"}:
        return v.title()
    return v

def _normalize_filters(filters: dict) -> dict:
    normalized = {}
    for k, v in (filters or {}).items():
        if v is None:
            continue
        vv = _normalize_filter_value(k, str(v))
        if vv:
            normalized[k] = vv
    return normalized

def get_db():
    global client
    if not MONGODB_URI:
        return None
    if not client:
        try:
            client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            return None
    return client[DB_NAME]

try:
    from sentence_transformers import SentenceTransformer
    logger.info("Loading SentenceTransformer local embedding model...")
    _embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    logger.info("SentenceTransformer model loaded successfully!")
except Exception as e:
    logger.error(f"Failed to load SentenceTransformer: {e}")
    _embed_model = None

def get_hf_embeddings(text: str) -> list[float]:
    """Generates embeddings using local SentenceTransformer model."""
    start_t = time.time()
    if _embed_model is None:
        logger.error("SentenceTransformer model not loaded!")
        return []
    
    try:
        embedding = _embed_model.encode(text, normalize_embeddings=True)
        logger.info(f"[SPEED] Local embedding took {time.time() - start_t:.3f}s")
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Local Embedding Exception: {e}")
        return []

def get_embedder():
    """Reserved for legacy/local if needed, but we prefer HF API now."""
    return None

def _embed_query(text: str) -> list[float]:
    key = (text or "").strip()
    if not key:
        return []
    cached = _cache_get(_embed_cache, key, EMBED_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached
    
    # Use HF API
    vec = get_hf_embeddings(key)
    
    if vec:
        _cache_set(_embed_cache, key, vec)
        _cache_prune(_embed_cache, EMBED_CACHE_TTL_SECONDS)
    return vec

_PROMPT_INJECTION_PATTERNS = [
    r"ignore (all|any|previous) instructions",
    r"system prompt",
    r"developer message",
    r"you are chatgpt",
    r"reveal (the )?secret",
    r"BEGIN (SYSTEM|INSTRUCTIONS)",
    r"END (SYSTEM|INSTRUCTIONS)",
]

def _sanitize_web_text(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", str(text)).strip()
    t = re.sub(r"https?://\S+", "", t)
    # remove common prompt-injection cues
    for pat in _PROMPT_INJECTION_PATTERNS:
        t = re.sub(pat, "[redacted]", t, flags=re.IGNORECASE)
    return t.strip()

def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20].rstrip() + " …(truncated)"

def web_search_fallback(query: str) -> str:
    """Performs a web search using DuckDuckGo as a fallback for missing data."""
    if not WEB_FALLBACK_ENABLED:
        return ""
    logger.info(f"[RAG] Triggering Web Fallback for: {query}")
    try:
        with DDGS() as ddgs:
            # We specifically look for Kanan International context if it's about people/services
            search_query = f"Kanan International {query}" if "kanan" not in query.lower() else query
            results = list(ddgs.text(search_query, max_results=WEB_MAX_RESULTS))
            
            if not results:
                return ""
                
            formatted_results = []
            for r in results:
                href = _sanitize_web_text(r.get("href") or "")
                body = _sanitize_web_text(r.get("body") or "")
                if not body:
                    continue
                formatted_results.append(f"Source: {href}\nContent: {body}")
            
            return _truncate("\n---\n".join(formatted_results), WEB_MAX_CHARS)
    except Exception as e:
        logger.error(f"[WebSearch] Error: {e}")
        return ""

def rewrite_query(query: str, chat_history: list = None) -> tuple[str, str, dict]:
    """Uses Groq to extract a semantic query and a metadata filters dictionary."""
    history_tail = ""
    if chat_history:
        try:
            history_tail = json.dumps(chat_history[-6:], ensure_ascii=False)
        except Exception:
            history_tail = ""
    cache_key = f"{query}\n{history_tail}"
    cached = _cache_get(_rewrite_cache, cache_key, REWRITE_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    history_text = ""
    if chat_history:
        for msg in chat_history[-6:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('content')}\n"
            
    try:
        from analytics import get_schema_profile
        schema = get_schema_profile()
        valid_keys = list(schema.keys())
        valid_values_str = ""
        for k, vals in schema.items():
            valid_values_str += f"- {k}: {vals[:15]}\n" 
    except Exception as e:
        logger.error(f"Failed to load schema for prompt: {e}")
        valid_keys = []
        valid_values_str = "No specific filter schema available."
        
    prompt = f"""Given the following conversation history and latest query, extract:
1. `search_query`: A string for semantic search (names, general topics).
2. `keyword`: IF the user mentions a specific proper noun, company name, agent name, or part of a name, extract that exact snippet here. 
3. `filters`: A dictionary of exact match filters. Valid keys: {valid_keys}.

Valid values to choose from for filters:
{valid_values_str}

Return ONLY a valid JSON object with the keys 'search_query', 'keyword', and 'filters'.

Conversation History:
{history_text}
Latest Query: {query}
"""

    try:
        response = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a JSON query extractor. Return ONLY valid JSON."}, 
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        
        search_query = data.get("search_query", query)
        keyword = str(data.get("keyword", "")).strip()
        filters = data.get("filters", {})
        
        out = (search_query, keyword, filters)
        _cache_set(_rewrite_cache, cache_key, out)
        _cache_prune(_rewrite_cache, REWRITE_CACHE_TTL_SECONDS)
        return out
    except Exception as e:
        logger.error(f"[RAG] Query rewrite failed: {e}")
        return query, "", {}

def retrieve_from_mongo(search_query: str, keyword: str, filters: dict, max_results: int = 15) -> list:
    db = get_db()
    if db is None:
        return []
        
    collection = db[COLLECTION_NAME]
    results_docs = []

    match_conditions = {}
    if filters:
        filters = _normalize_filters(filters)
        for k, v in filters.items():
            match_conditions[k] = {"$regex": f"^{v}$", "$options": "i"}
            
    if keyword:
        # Escape the keyword so valid special character searches (e.g. A C & Co) do not break the regex engine
        safe_kw = re.escape(keyword)
        match_conditions["$or"] = [
            {"account_name": {"$regex": safe_kw, "$options": "i"}},
            {"text": {"$regex": safe_kw, "$options": "i"}}
        ]

    try:
        # Keyword Search
        if match_conditions:
            cursor = collection.find(match_conditions).limit(max_results)
            for doc in cursor:
                results_docs.append(doc.get("text"))
            
        # Vector Search (Atlas)
        if search_query:
            query_vector = _embed_query(search_query)
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": 100,
                        "limit": max_results
                    }
                }
            ]
            
            try:
                vector_results = list(collection.aggregate(pipeline))
                for doc in vector_results:
                    val = doc.get("text")
                    if val not in results_docs:
                        results_docs.append(val)
            except OperationFailure as e:
                # Fallback to text search if vector index missing or not enabled
                if not match_conditions:
                   words = search_query.split()
                   regex_pattern = "|".join([re.escape(w) for w in words])
                   cursor = collection.find({"text": {"$regex": regex_pattern, "$options": "i"}}).limit(max_results)
                   for doc in cursor:
                       val = doc.get("text")
                       if val not in results_docs:
                           results_docs.append(val)
            except Exception as e:
                logger.error(f"[RAG] Vector search failed: {e}")
                   
    except Exception as e:
        logger.error(f"[RAG] MongoDB retrieval failed: {e}")

    return results_docs

def _check_vector_index_available(collection) -> tuple[bool, str | None]:
    global _vector_index_available
    if _vector_index_available is not None:
        return _vector_index_available, None
    try:
        # Minimal no-op vectorSearch check; will throw if index missing.
        pipeline = [{
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": [0.0] * 384,
                "numCandidates": 1,
                "limit": 1
            }
        }]
        list(collection.aggregate(pipeline))
        _vector_index_available = True
        return True, None
    except OperationFailure as e:
        _vector_index_available = False
        return False, "MongoDB Atlas vector index 'vector_index' not available. Falling back to regex search."
    except Exception as e:
        _vector_index_available = False
        return False, f"Vector search unavailable: {e}"

def retrieve_context(query: str, chat_history: list = None, n_results: int = 40) -> str:
    """
    Hybrid Search Strategy: Static KB -> MongoDB -> Web Fallback
    """
    # 1. Search Static KB first (FAQs and Leadership)
    kb_context = get_kb_context(query)
    
    # 2. Enrich query and search MongoDB Atlas
    enriched_query, keyword, filters = rewrite_query(query, chat_history)
    db_results = retrieve_from_mongo(enriched_query, keyword, filters, max_results=n_results)
    
    db_context = "\n---\n".join(db_results[:n_results]) if db_results else ""
    
    # 3. Web Fallback: Trigger if DB is empty OR for high-priority 'current' queries
    web_context = ""
    query_lower = query.lower()
    priority_keywords = ["latest", "update", "news", "current", "visa", "permit", "result", "canada study"]
    is_priority = any(k in query_lower for k in priority_keywords)
    
    if (not db_results and len(query.split()) > 2) or is_priority:
        logger.info(f"[RAG] Priority web search triggered for: {query}")
        web_context = web_search_fallback(query)
        
    # Combine contexts
    final_context = []
    if kb_context:
        final_context.append(f"--- INTERNAL KNOWLEDGE --- \n{kb_context}")
    if db_context:
        final_context.append(f"--- DATABASE RECORDS --- \n{db_context}")
    if web_context:
        final_context.append(f"--- WEB RESULTS --- \n{web_context}")
        
    if not final_context:
        return "I couldn't find specific information in the database or online. However, I can help you with general study abroad guidance based on Kanan's core services."

    return "\n\n".join(final_context)

def retrieve_context_with_meta(query: str, chat_history: list = None, n_results: int = 40) -> tuple[str, dict]:
    meta = {"warnings": [], "filters": {}, "keyword": "", "mode": get_current_mode()}

    kb_context = get_kb_context(query)

    if meta["mode"] == "offline":
        meta["sources"] = ["kb"] if kb_context else []
        return (f"--- INTERNAL KNOWLEDGE (OFFLINE) --- \n{kb_context}" if kb_context else "No local information found."), meta

    enriched_query, keyword, filters = rewrite_query(query, chat_history)
    filters = _normalize_filters(filters)
    meta["filters"] = filters
    meta["keyword"] = keyword

    db = get_db()
    if db is None:
        meta["warnings"].append("MongoDB is not configured or not reachable.")
        db_results = []
    else:
        collection = db[COLLECTION_NAME]
        ok, warn = _check_vector_index_available(collection)
        if not ok and warn:
            meta["warnings"].append(warn)
        db_results = retrieve_from_mongo(enriched_query, keyword, filters, max_results=n_results)

    db_context = "\n---\n".join(db_results[:n_results]) if db_results else ""

    web_context = ""
    query_lower = query.lower()
    priority_keywords = ["latest", "update", "news", "current", "visa", "permit", "result", "canada study"]
    is_priority = any(k in query_lower for k in priority_keywords)
    if (not db_results and len(query.split()) > 2) or is_priority:
        web_context = web_search_fallback(query)

    sources = []
    if kb_context:
        sources.append("kb")
    if db_context:
        sources.append("db")
    if web_context:
        sources.append("web")
    meta["sources"] = sources

    final_context = []
    if kb_context:
        final_context.append(f"--- INTERNAL KNOWLEDGE --- \n{kb_context}")
    if db_context:
        final_context.append(f"--- DATABASE RECORDS --- \n{db_context}")
    if web_context:
        final_context.append(f"--- WEB RESULTS --- \n{web_context}")
    if not final_context:
        return "I couldn't find specific information in the database or online. However, I can help you with general study abroad guidance based on Kanan's core services.", meta
    return "\n\n".join(final_context), meta
