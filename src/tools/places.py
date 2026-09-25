import json
import re
import urllib.parse
from duckduckgo_search import DDGS
from google import genai
from google.genai import types

from src.config import MODEL_NAME, GEMINI_API_KEY

VENUE_PROFILES = {
    "Chandanagar": {"areas": ["Chandanagar", "Gangaram", "BHEL"]},
    "Miyapur": {"areas": ["Miyapur", "Kondapur", "Lingampally"]},
    "Kondapur": {"areas": ["Kondapur", "Miyapur", "Gachibowli"]},
    "Gachibowli": {"areas": ["Gachibowli", "Financial District"]},
}

EXCLUDED_VENUE_TERMS = (
    "gmc balayogi",
    "gachibowli stadium",
    "kompally",
    "secunderabad",
)


def _get_gemini_client():
    if not GEMINI_API_KEY:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEY)
    except (TypeError, ValueError):
        return None


def _distance_km(distance: object) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*km", str(distance).lower())
    return float(match.group(1)) if match else None


def _is_allowed_venue(venue: dict, locality: str) -> bool:
    name = str(venue.get("name", "")).strip()
    haystack = f"{name} {venue.get('address', '')} {venue.get('area', '')}".lower()
    profile = VENUE_PROFILES.get(locality, {"areas": [locality]})
    area_match = any(area.lower() in haystack for area in profile["areas"])
    distance = _distance_km(venue.get("distance"))
    return bool(name and area_match and distance is not None and distance <= 6 and not any(term in haystack for term in EXCLUDED_VENUE_TERMS))

def geocode_location(location_query: str) -> tuple[float, float, str]:
    """Resolves coordinates and locality names."""
    if not location_query:
        return 0.0, 0.0, "Location required"
    if "chandanagar" in location_query.lower():
        return 17.4947, 78.3428, "Chandanagar"
    elif "miyapur" in location_query.lower():
        return 17.4968, 78.3614, "Miyapur"
    elif "kondapur" in location_query.lower():
        return 17.4699, 78.3578, "Kondapur"
    elif "gachibowli" in location_query.lower():
        return 17.4401, 78.3489, "Gachibowli"
    
    # Check for latitude,longitude numbers
    parts = location_query.split(",")
    if len(parts) == 2:
        try:
            return float(parts[0].strip()), float(parts[1].strip()), "Detected Neighborhood"
        except ValueError:
            pass

    return 0.0, 0.0, "Location required"

def search_grounded_venues(sub_activity: str, locality: str, lat: float, lon: float, exclude_names: list = None) -> list[dict]:
    """Fetches strictly 3 grounded local spots within 6km radius."""
    client = _get_gemini_client()
    if client is None:
        return []

    exclude_names = exclude_names or []
    profile = VENUE_PROFILES.get(locality, {"areas": [locality]})
    query = f"best {sub_activity} in {' or '.join(profile['areas'])} Hyderabad verified venues"

    search_snippets = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6))
            search_snippets = "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
    except Exception:
        search_snippets = f"Top rated {sub_activity} spots in {locality}, Hyderabad."

    prompt = f"""
You are an expert hyper-local venue curator for Hyderabad, India.
User query: {sub_activity} near {locality} (Latitude: {lat}, Longitude: {lon}).

Grounding snippets:
{search_snippets}

CRITICAL RULES:
1. Return EXACTLY 3 (THREE) real, verified venues. DO NOT return 4.
2. Venues MUST be within 6 km of {locality}; allowed areas are ONLY {json.dumps(profile['areas'])}.
3. STRICTLY EXCLUDE generic government stadiums (GMC Balayogi, Gachibowli Stadium) and far-off locations (Kompally, Secunderabad).
4. Do not include any of these already shown venues: {json.dumps(exclude_names)}

Output strictly valid JSON (list of 3 objects):
[
  {{
    "name": "Venue Name",
    "distance": "e.g., 2.1 km",
    "travel_time": "e.g., 8 mins drive",
    "status": "e.g., Open until 11:30 PM",
    "cost": "e.g., ₹400 for two / ₹800 per hr turf",
    "amenities": "e.g., Floodlights, Parking, AstroTurf",
    "highlights": "Specific one-sentence highlight about this venue",
    "area": "Neighborhood or immediate locality"
  }}
]
"""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        venues = json.loads(response.text.strip())
        if isinstance(venues, list):
            venues = [v for v in venues if isinstance(v, dict) and _is_allowed_venue(v, locality)][:3]
            if len(venues) == 3:
                for v in venues:
                    q = urllib.parse.quote_plus(f"{v['name']} {locality} Hyderabad")
                    v["directions_link"] = f"https://www.google.com/maps/search/?api=1&query={q}"
                return venues
    except Exception:
        pass

    # Never substitute hard-coded venues when live grounding fails.
    selected_list = []
    for v in selected_list:
        q = urllib.parse.quote_plus(f"{v['name']} {locality} Hyderabad")
        v["directions_link"] = f"https://www.google.com/maps/search/?api=1&query={q}"
    return selected_list
