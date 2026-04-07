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

def _get_collection():
    global _client
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI not set")
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return _client[DB_NAME][COLLECTION_NAME]

def get_summary():
    col = _get_collection()
    total = col.count_documents({})
    active = col.count_documents({"active": "Yes"})
    zones = len(col.distinct("zone"))
    cities = len(col.distinct("city"))
    ranks = len(col.distinct("rank"))
    return {
        "total_agents": total,
        "active_agents": active,
        "active_rate": round((active / total * 100), 1) if total else 0,
        "zones": zones,
        "cities": cities,
        "ranks": ranks,
    }

def get_by_zone():
    col = _get_collection()
    pipeline = [
        {"$match": {"zone": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$zone", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_by_rank():
    col = _get_collection()
    pipeline = [
        {"$match": {"rank": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$rank", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_by_city(limit=15):
    col = _get_collection()
    pipeline = [
        {"$match": {"city": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$city", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_by_category():
    col = _get_collection()
    pipeline = [
        {"$match": {"category": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_active_status():
    col = _get_collection()
    pipeline = [
        {"$group": {"_id": "$active", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"] or "Unknown", "value": r["count"]} for r in results]

def get_by_team(limit=15):
    col = _get_collection()
    pipeline = [
        {"$match": {"team": {"$ne": "Unknown"}}},
        {"$group": {"_id": "$team", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    results = list(col.aggregate(pipeline))
    return [{"name": r["_id"], "value": r["count"]} for r in results]

def get_all_analytics():
    """Returns all analytics data in a single response for efficiency."""
    try:
        return {
            "summary": get_summary(),
            "by_zone": get_by_zone(),
            "by_rank": get_by_rank(),
            "by_city": get_by_city(),
            "by_category": get_by_category(),
            "active_status": get_active_status(),
            "by_team": get_by_team(),
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise
