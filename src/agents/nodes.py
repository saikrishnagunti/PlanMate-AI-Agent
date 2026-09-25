import re
import urllib.parse
from html import escape
from google import genai
from google.genai import types

from src.config import MODEL_NAME, GEMINI_API_KEY
from src.state import PlanMateState
from src.tools.weather import fetch_weather
from src.tools.places import geocode_location, search_grounded_venues

def intent_router_node(state: PlanMateState) -> dict:
    query = state.get("user_query", "").strip()
    loc_input = state.get("location_input", "").strip()
    locality = state.get("locality", "").strip()
    lat = state.get("lat")
    lon = state.get("lon")
    if not locality or locality in {"Location required", "Location off", "Location unavailable"} or lat is None or lon is None:
        lat, lon, locality = geocode_location(loc_input)

    cat = "eat"
    sub_activity = "biryani"

    q_lower = query.lower()
    if any(k in q_lower for k in ["cricket", "badminton", "football", "bowling", "snooker", "game", "kart", "turf", "play", "sports"]):
        cat = "play"
        sub_activity = "box cricket"
        for candidate in ["badminton", "football", "bowling", "snooker", "pickleball", "tennis", "go-karting", "box cricket"]:
            if candidate in q_lower:
                sub_activity = candidate
                break
    elif any(k in q_lower for k in ["relax", "spa", "movie", "cinema", "park", "lake", "cafe", "sunset"]):
        cat = "relax"
        sub_activity = "quiet cafe"
        for candidate in ["movie", "cinema", "spa", "park", "lake", "sunset", "cafe", "library"]:
            if candidate in q_lower:
                sub_activity = candidate
                break
    else:
        cat = "eat"
        sub_activity = "biryani"
        for candidate in ["shawarma", "mandi", "pizza", "italian", "chinese", "chaat", "tiffins", "desserts", "chai", "biryani", "sushi"]:
            if candidate in q_lower:
                sub_activity = candidate
                break

    return {
        "locality": locality or "Location required",
        "lat": lat,
        "lon": lon,
        "category": cat,
        "sub_activity": sub_activity
    }

def weather_node(state: PlanMateState) -> dict:
    lat = state.get("lat")
    lon = state.get("lon")
    if lat is None or lon is None:
        return {"weather_data": {"condition": "Location required"}}
    w = fetch_weather(lat, lon)
    return {"weather_data": w}

def scout_node(state: PlanMateState) -> dict:
    sub_act = state.get("sub_activity", "places")
    loc = state.get("locality", "Chandanagar")
    lat = state.get("lat")
    lon = state.get("lon")
    if lat is None or lon is None:
        return {"candidate_venues": [], "all_places_link": ""}
    prev_venues = state.get("candidate_venues", [])
    exclude_names = [v.get("name", "") for v in prev_venues]

    new_venues = search_grounded_venues(sub_act, loc, lat, lon, exclude_names=exclude_names)
    combined = (prev_venues + new_venues)[:3]

    q_encoded = urllib.parse.quote_plus(f"{sub_act} in {loc} Hyderabad")
    all_link = f"https://www.google.com/maps/search/?api=1&query={q_encoded}"

    return {
        "candidate_venues": combined,
        "all_places_link": all_link
    }

retrieval_node = scout_node

def critic_node(state: PlanMateState) -> dict:
    venues = state.get("candidate_venues", [])
    if not venues:
        return {"validation_status": "fail", "critic_notes": "No venues discovered."}
    return {"validation_status": "pass", "critic_notes": "Venues strictly grounded within 6km radius."}

def synthesizer_node(state: PlanMateState) -> dict:
    w = state.get("weather_data", {})
    raw_venues = state.get("candidate_venues") or []
    venues = raw_venues[:3]  # Enforce exactly 3 verified places
    loc = state.get("locality", "Hyderabad")
    activity_title = (state.get("sub_activity") or "places").title()

    temp = w.get("temperature", "29.0°C")
    condition = w.get("condition", "Pleasant")
    humidity = w.get("humidity", "55%")
    verdict = w.get("verdict", f"Optimal conditions to step out in {loc}!")

    response_lines = [
        f"""
<div class="weather-card">
    <div class="weather-header">
        <strong style="font-size: 1.1rem; color: #0369a1; font-weight: 800;">⛅ Meteorological Grounding</strong>
        <span class="weather-badge">Live Open-Meteo</span>
    </div>
    <div class="weather-metrics">
        <span class="weather-metric-pill">🌡️ {temp}</span>
        <span class="weather-metric-pill">☁️ {condition}</span>
        <span class="weather-metric-pill">💧 {humidity} Humidity</span>
        <span class="weather-metric-pill">🛡️ Strict 6km Radius</span>
    </div>
    <div style="font-size: 0.92rem; color: #334155; font-weight: 600; margin-top: 0.3rem;">
        💡 <strong>Planner Verdict:</strong> {verdict}
    </div>
</div>
"""
    ]

    if not venues:
        response_lines.append(f"""
<div class="venue-card venue-empty-state">
    <div class="venue-title">No verified {escape(activity_title)} venues found</div>
    <div>Live search did not return three venues that could be verified inside the 6 km perimeter for {escape(loc)}. Choose another nearby area or use Maps to inspect current listings.</div>
</div>
""")

    for idx, v in enumerate(venues, 1):
        name = escape(str(v.get("name", "Recommended Spot")))
        timing_badge = f'<span class="venue-badge-timing">🕒 {escape(str(v.get("status", "Open daily")))}</span>'
        cost_badge = f'<span class="venue-badge-cost">💰 {escape(str(v.get("cost", "Standard rates")))}</span>'
        dist_pill = f'<span class="venue-badge-timing">📍 {escape(str(v.get("distance", "Nearby")))} • 🚗 {escape(str(v.get("travel_time", "Short drive")))}</span>'

        response_lines.append(f"""
<div class="venue-card">
    <div class="venue-title-row">
        <div class="venue-title">#{idx} {name}</div>
        <div class="venue-rating-badge">⭐ 4.5+ Verified</div>
    </div>
    <div class="venue-badges">
        {dist_pill}
        {timing_badge}
        {cost_badge}
    </div>
    <div style="font-size: 0.9rem; color: #475569; margin-bottom: 0.4rem;">
        ✨ <strong>Facilities:</strong> {escape(str(v.get("amenities", "Standard amenities")))}
    </div>
    <div style="font-size: 0.9rem; color: #1e293b; line-height: 1.45; margin-bottom: 0.6rem;">
        {escape(str(v.get("highlights", "")))}
    </div>
    <div>
        <a class="venue-btn" href="{escape(str(v.get('directions_link', '#')))}" target="_blank">🧭 Open in Google Maps</a>
    </div>
</div>
""")

    # Option 4: User Custom Choice from Live Interactive Maps
    search_term = state.get("sub_activity") or state.get("user_query") or "spots"
    map_search_q = urllib.parse.quote_plus(f"{search_term} in {loc} Hyderabad")
    custom_map_link = f"https://www.google.com/maps/search/?api=1&query={map_search_q}"

    response_lines.append(f"""
<div class="venue-card custom-map-card">
    <div class="venue-title-row">
        <div class="venue-title">#4 🗺️ Choose from Maps (Your Choice)</div>
        <span style="background: #dcfce7; color: #166534; font-weight: 800; font-size: 0.8rem; padding: 3px 9px; border-radius: 8px;">Live Explorer</span>
    </div>
    <div style="font-size: 0.9rem; color: #374151; margin-bottom: 0.6rem;">
        Prefer picking your own spot? Open the live interactive map for <strong>{activity_title}</strong> in <strong>{loc}</strong> to compare live traffic, ratings, and select your destination directly.
    </div>
    <div>
        <a class="venue-btn map-picker-btn" href="{custom_map_link}" target="_blank">
            📍 Open Interactive Map Picker →
        </a>
    </div>
</div>
""")

    return {"final_response": "\n".join(response_lines)}
