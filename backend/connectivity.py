import os
import socket
import logging
import json
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def get_current_mode() -> str:
    """Always returns online for production cloud environment to prevent file-write crashes."""
    return "online"

def set_current_mode(mode: str):
    """Deprecated in Serverless Production. State is immutable."""
    pass

def is_internet_available() -> bool:
    """Checks if external internet is reachable by pinging Google DNS."""
    try:
        socket.setdefaulttimeout(3)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def is_internet_available() -> bool:
    """Checks if external internet is reachable by pinging Google DNS (non-blocking)."""
    try:
        # Use a very short timeout for cloud environments
        socket.setdefaulttimeout(1)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def get_system_status():
    """Returns a system status report without blocking on local services."""
    has_internet = is_internet_available()
    
    # Logic: Report degraded if internet is down (as external APIs are required)
    status = "online" if has_internet else "degraded (no internet)"
    
    return {
        "status": status,
        "internet": has_internet,
        "groq_key": bool(os.getenv("GROQ_API_KEY")),
        "atlas_uri": bool(os.getenv("MONGODB_URI")),
        "version": "2.0.0-cloud"
    }
