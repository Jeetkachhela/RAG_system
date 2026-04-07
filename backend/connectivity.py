import os
import socket
import logging
import json
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "app_config.json")

def get_current_mode() -> str:
    """Reads the current app mode (online or offline) from config, defaults to 'online'."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("mode", "online")
        except Exception as e:
            logger.error(f"Error reading config: {e}")
    return "online"

def set_current_mode(mode: str):
    """Saves the current app mode persistently."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"mode": mode}, f)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

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
    mode = get_current_mode()
    has_internet = is_internet_available()
    
    # Logic: Even if mode is set to 'online', if internet is down, report 'Degraded'
    status = mode
    if mode == "online" and not has_internet:
        status = "degraded (no internet)"
    
    return {
        "mode": mode,
        "status": status,
        "internet": has_internet,
        "groq_key": bool(os.getenv("GROQ_API_KEY")),
        "atlas_uri": bool(os.getenv("MONGODB_URI")),
        "version": "2.0.0-cloud"
    }
