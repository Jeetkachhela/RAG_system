import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "kanan_rag")
COLLECTION_NAME = "kanan_agents"

_client = None

def _get_client():
    global _client
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not set")
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client

def _get_collection():
    return _get_client()[DB_NAME][COLLECTION_NAME]

def _get_schema_collection():
    return _get_client()[DB_NAME]["kanan_schema"]

def _get_logs_collection():
    return _get_client()[DB_NAME]["chat_logs"]

def log_chat_query(query: str, latency: float = 0.0):
    try:
        col = _get_logs_collection()
        col.insert_one({
            "query": query,
            "latency": latency,
            "timestamp": datetime.now()
        })
    except Exception as e:
        logger.error(f"Failed to log chat query: {e}")

def get_usage_analytics():
    col = _get_logs_collection()
    total = col.count_documents({})
    
    pipeline = [
        {"$group": {"_id": "$query", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    
    try:
        top_queries = list(col.aggregate(pipeline))
    except Exception as e:
        logger.error(f"Failed to aggregate top queries: {e}")
        top_queries = []
        
    return {
        "total_queries": total,
        "top_queries": [{"name": str(q["_id"]), "value": q["count"]} for q in top_queries]
    }

def get_schema_profile():
    """Try to load schema from kanan_schema collection."""
    try:
        schema_col = _get_schema_collection()
        profile = schema_col.find_one({"type": "schema_profile"})
        if profile and "categorical_fields" in profile and profile["categorical_fields"]:
            return profile["categorical_fields"]
    except Exception as e:
        logger.warning(f"Could not load schema profile: {e}")
    return None

def _auto_detect_categorical_fields():
    """Fallback: scan actual documents to auto-detect categorical columns dynamically."""
    col = _get_collection()
    
    # Sample a document to discover all field names
    sample = col.find_one()
    if not sample:
        return {}

    # Fields to always skip (MongoDB internals + high-cardinality identifiers)
    skip_fields = {"_id", "text", "embedding", "vector"}
    skip_keywords = {"name", "date", "id", "no.", "number", "email", "phone", "code", "address", "url", "link"}
    
    categorical_fields = {}
    
    for field in sample.keys():
        if field in skip_fields:
            continue
        field_lower = field.lower()
        if any(kw in field_lower for kw in skip_keywords):
            continue
        
        # Count distinct non-null values
        try:
            distinct_vals = col.distinct(field)
            clean_vals = [
                v for v in distinct_vals 
                if v is not None and str(v).strip() != "" 
                and str(v).strip().lower() not in {"unknown", "nan", "none", "n/a"}
            ]
            # Only treat as categorical if between 1 and 35 unique values
            if 1 <= len(clean_vals) <= 35:
                categorical_fields[field] = sorted([str(v) for v in clean_vals])
        except Exception as e:
            logger.warning(f"Could not get distinct values for field '{field}': {e}")
            continue
    
    logger.info(f"Auto-detected {len(categorical_fields)} categorical fields: {list(categorical_fields.keys())}")
    return categorical_fields

def get_dynamic_distribution(field_name, limit=20):
    col = _get_collection()
    pipeline = [
        {"$match": {field_name: {"$nin": ["Unknown", "nan", "None", "", None]}}},
        {"$group": {"_id": f"${field_name}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": str(r["_id"]), "value": r["count"]} for r in results]

def get_dynamic_summary(categorical_fields):
    col = _get_collection()
    total = col.count_documents({})
    
    summary = {
        "total_documents": total,
    }
    
    if total == 0:
        return summary
    
    # Active rate calculation (if a boolean/Yes-No "Active" column exists)
    active_col = next((k for k in categorical_fields.keys() if k.lower() == "active"), None)
    if active_col:
        active_count = col.count_documents({active_col: "Yes"})
        summary["active_documents"] = active_count
        summary["active_rate"] = round((active_count / total * 100), 1) if total > 0 else 0
        
    for field in categorical_fields.keys():
        try:
            distinct_count = len([
                x for x in col.distinct(field) 
                if x and str(x).strip().lower() not in {"unknown", "nan", "none", ""}
            ])
            summary[f"unique_{field}"] = distinct_count
        except Exception as e:
            logger.warning(f"Could not count distinct for '{field}': {e}")
        
    return summary

def get_all_analytics():
    """Returns dynamic analytics data based on the discovered schema.
    Falls back to auto-detection if no schema profile exists."""
    try:
        # Try stored schema first, then auto-detect
        categorical_fields = get_schema_profile()
        if not categorical_fields:
            logger.info("No schema profile found, auto-detecting from data...")
            categorical_fields = _auto_detect_categorical_fields()
        
        if not categorical_fields:
            logger.warning("No categorical fields found in data")
            return {"summary": {"total_documents": _get_collection().count_documents({})}, "distributions": {}}
        
        response = {
            "summary": get_dynamic_summary(categorical_fields),
            "distributions": {},
            "usage": get_usage_analytics()
        }
        
        for field in categorical_fields.keys():
            dist = get_dynamic_distribution(field)
            if dist:  # Only include non-empty distributions
                response["distributions"][field] = dist
                
        return response
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        raise
