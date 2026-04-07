import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

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

def get_schema_profile():
    schema_col = _get_schema_collection()
    profile = schema_col.find_one({"type": "schema_profile"})
    if profile and "categorical_fields" in profile:
        return profile["categorical_fields"]
    return {}

def get_dynamic_distribution(field_name, limit=20):
    col = _get_collection()
    pipeline = [
        {"$match": {field_name: {"$nin": ["Unknown", "nan", "None", "", None]}}},
        {"$group": {"_id": f"${field_name}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_dynamic_summary(categorical_fields):
    col = _get_collection()
    total = col.count_documents({})
    
    summary = {
        "total_documents": total,
    }
    
    # Active rate calculation (if a boolean/Yes-No "Active" column exists)
    active_col = next((k for k in categorical_fields.keys() if k.lower() == "active"), None)
    if active_col:
        active_count = col.count_documents({active_col: "Yes"})
        summary["active_documents"] = active_count
        summary["active_rate"] = round((active_count / total * 100), 1) if total > 0 else 0
        
    for field in categorical_fields.keys():
        distinct_count = len([x for x in col.distinct(field) if x and str(x).lower() not in ["unknown", "nan", "none", ""]])
        summary[f"unique_{field}"] = distinct_count
        
    return summary

def get_all_analytics():
    """Returns dynamic analytics data based on the discovered schema."""
    try:
        categorical_fields = get_schema_profile()
        
        response = {
            "summary": get_dynamic_summary(categorical_fields),
            "distributions": {}
        }
        
        for field in categorical_fields.keys():
            response["distributions"][field] = get_dynamic_distribution(field)
            
        return response
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise
