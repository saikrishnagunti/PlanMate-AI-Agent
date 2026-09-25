import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Pin explicitly to gemini-3.5-flash-lite
MODEL_NAME = "gemini-3.5-flash-lite"


def _load_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    try:
        import streamlit as st

        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        return ""


GEMINI_API_KEY = _load_gemini_api_key()

# Default spatial coordinates (Hyderabad central fallback)
DEFAULT_LAT = 17.4435
DEFAULT_LON = 78.3772
DEFAULT_LOCALITY = "Hyderabad"

# Critic Agent limits
MAX_SCOUT_RETRIES = 2

# Semantic Blacklists to prevent cuisine & sports hallucinations
SEMANTIC_BLACKLISTS = {
    "italian": ["chinese", "mandi", "biryani", "dhaba", "mess", "bawarchi", "curry", "tiffin", "south indian"],
    "pizza": ["chinese", "mandi", "biryani", "dhaba", "mess", "tiffin"],
    "sushi": ["dhaba", "pizza", "biryani", "burger", "tiffin", "mess", "curry"],
    "continental": ["dhaba", "biryani", "tiffin", "mess"],
    "cricket": ["gym", "spa", "salon", "hotel", "restaurant", "swimming pool"],
    "badminton": ["gym", "spa", "salon", "hotel", "snooker"],
}
