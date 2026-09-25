from pathlib import Path
import random
import re
import urllib.parse
import requests
import streamlit as st
import streamlit.components.v1 as components
from src.config import GEMINI_API_KEY
from src.tools.weather import fetch_weather
from src.agents.graph import planmate_graph

location_component = components.declare_component(
    "planmate_location",
    path=str(Path(__file__).resolve().parent / "src" / "components" / "frontend" / "build"),
)

# ---------------------------------------------------------
# Page Setup: Widescreen Mode
# ---------------------------------------------------------
st.set_page_config(
    page_title="PlanMate AI | Autonomous Day Planner",
    page_icon="🎯",
    layout="wide"
)

if not GEMINI_API_KEY:
    st.warning("Gemini API key is not configured. Add GEMINI_API_KEY to Streamlit Cloud Secrets to enable venue recommendations.")

# Load CSS
css_path = Path(__file__).resolve().parent / "styles" / "main.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------
# Resolve Avatars
# ---------------------------------------------------------
assets_dir = Path(__file__).resolve().parent / "assets"

def get_avatar_path(role: str) -> str:
    exts = [".jpg", ".jpeg", ".png", ".avif", ".webp"]
    for ext in exts:
        cand = assets_dir / f"{role}{ext}"
        if cand.exists():
            return str(cand)
    return "🐱" if role == "user" else "🤖"

USER_AVATAR = get_avatar_path("user")
ASSISTANT_AVATAR = get_avatar_path("assistant")


def resolve_map_location(location_input: str):
    """Resolve a pasted Maps URL, address, locality, or coordinate pair."""
    raw_value = location_input.strip()
    if not raw_value:
        return None

    parsed = urllib.parse.urlparse(raw_value)
    query_params = urllib.parse.parse_qs(parsed.query)
    query_values = query_params.get("query", []) or query_params.get("q", [])
    search_text = urllib.parse.unquote_plus(query_values[0]) if query_values else raw_value

    coordinate_patterns = [
        r"(?:@|!3d)(-?\d+(?:\.\d+)?)[,/]?(?:!4d)?(-?\d+(?:\.\d+)?)",
        r"(?:ll|center)=(-?\d+(?:\.\d+)?)[, ]+(-?\d+(?:\.\d+)?)",
        r"^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$",
    ]
    coordinate_match = next(
        (
            re.search(pattern, candidate)
            for candidate in (raw_value, search_text)
            for pattern in coordinate_patterns
            if re.search(pattern, candidate)
        ),
        None,
    )
    if coordinate_match:
        lat = float(coordinate_match.group(1))
        lon = float(coordinate_match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return resolve_coordinates(lat, lon)

    if parsed.path and "/maps/" in raw_value and not query_values:
        search_text = urllib.parse.unquote(parsed.path.rsplit("/place/", 1)[-1]).replace("+", " ")

    lowered = search_text.lower()
    for locality, data in LOCALITY_DATA.items():
        if locality.lower() in lowered:
            return data["lat"], data["lon"], locality, None

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{search_text}, Hyderabad, India", "format": "json", "limit": 1},
            headers={"User-Agent": "PlanMate-AI/1.0"},
            timeout=8,
        )
        result = response.json()[0]
        label = result.get("display_name", search_text).split(",")[0].strip()
        address = result.get("address", {})
        nearby_areas = []
        for field in ("neighbourhood", "suburb", "city_district", "town", "municipality"):
            area = address.get(field)
            if area and area.lower() != label.lower() and area not in nearby_areas:
                nearby_areas.append(area)
        custom_data = {
            "lat": float(result["lat"]),
            "lon": float(result["lon"]),
            "coords": f"{result['lat']},{result['lon']}",
            "intel": ["Location selected from your Google Maps choice."],
            "spotlights": [],
            "nearby_areas": nearby_areas[:3],
        }
        return custom_data["lat"], custom_data["lon"], label, custom_data
    except (IndexError, KeyError, TypeError, ValueError, requests.RequestException):
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def reverse_geocode(lat: float, lon: float):
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18},
            headers={"User-Agent": "PlanMate-AI/1.0"},
            timeout=8,
        )
        result = response.json()
        address = result.get("address", {})
        label = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("city_district")
            or address.get("town")
            or "Live Location"
        )
        nearby_areas = []
        for field in ("neighbourhood", "suburb", "city_district", "town", "municipality"):
            area = address.get(field)
            if area and area.lower() != label.lower() and area not in nearby_areas:
                nearby_areas.append(area)
        return label, result.get("display_name", label), nearby_areas[:3]
    except (KeyError, TypeError, requests.RequestException, ValueError):
        return "Live Location", "Live Location", []


def resolve_coordinates(lat: float, lon: float):
    label, display_name, nearby_areas = reverse_geocode(lat, lon)
    for locality, data in LOCALITY_DATA.items():
        if locality.lower() in f"{label} {display_name}".lower():
            return data["lat"], data["lon"], locality, None
    custom_data = {
        "lat": lat,
        "lon": lon,
        "coords": f"{lat},{lon}",
        "intel": ["Location selected from your live or Google Maps location."],
        "spotlights": [],
        "nearby_areas": nearby_areas,
    }
    return lat, lon, label, custom_data

# ---------------------------------------------------------
# Dynamic Locality-Driven Intelligence Data
# ---------------------------------------------------------
LOCALITY_DATA = {
    "Chandanagar": {
        "lat": 17.4947, "lon": 78.3428,
        "coords": "17.4947,78.3428",
        "intel": [
            "Heavy evening street-food and chaat rush on the main road after 7 PM.",
            "Popular family dining hubs around Gangaram and BHEL circle.",
            "Quick access to Madeenaguda and NH-65 commercial stretch."
        ],
        "spotlights": [
            {"name": "🍲 Pista House Mandi", "desc": "Famous Mutton Juicy Mandi & Biryani", "url": "https://www.google.com/maps/search/?api=1&query=Pista+House+Chandanagar+Hyderabad"},
            {"name": "🏏 DRS Box Cricket", "desc": "Nearby Miyapur boundary • 24/7 Floodlit Turf", "url": "https://www.google.com/maps/search/?api=1&query=DRS+Box+Cricket+Miyapur+Hyderabad"},
            {"name": "☕ The Food Planet", "desc": "Late-night grills, tiffins & shawarma", "url": "https://www.google.com/maps/search/?api=1&query=The+Food+Planet+Chandanagar+Hyderabad"}
        ]
    },
    "Miyapur": {
        "lat": 17.4968, "lon": 78.3614,
        "coords": "17.4968,78.3614",
        "intel": [
            "Hub for box cricket turfs and multi-sport night arenas.",
            "Metro station vicinity is packed with late-night food stalls and cafes.",
            "Direct 10-minute link to Bachupally and Hafeezpet borders."
        ],
        "spotlights": [
            {"name": "🏏 Sky Turf Box Cricket", "desc": "All-weather AstroTurf • High netting pitch", "url": "https://www.google.com/maps/search/?api=1&query=Sky+Turf+Box+Cricket+Miyapur+Hyderabad"},
            {"name": "🥘 Mandi King Arabian", "desc": "Authentic chicken fahm and fragrant mandi rice", "url": "https://www.google.com/maps/search/?api=1&query=Mandi+King+Miyapur+Hyderabad"},
            {"name": "🎬 Cinepolis GSM Mall", "desc": "Premium multiplex screens & food court", "url": "https://www.google.com/maps/search/?api=1&query=Cinepolis+GSM+Mall+Miyapur+Hyderabad"}
        ]
    },
    "Kondapur": {
        "lat": 17.4699, "lon": 78.3578,
        "coords": "17.4699,78.3578",
        "intel": [
            "Vibrant cafe culture and specialty artisanal roasteries around RTO road.",
            "Close proximity to Pala Pitta Cycling Park & botanical walking trails.",
            "Active fitness, badminton academies, and sports complexes."
        ],
        "spotlights": [
            {"name": "☕ Roast CCX / Comic Social", "desc": "Aesthetic specialty brew cafe with board games", "url": "https://www.google.com/maps/search/?api=1&query=Roast+CCX+Kondapur+Hyderabad"},
            {"name": "🏸 Gamepoint Arena", "desc": "Badminton, basketball & indoor sports courts", "url": "https://www.google.com/maps/search/?api=1&query=Gamepoint+Kondapur+Hyderabad"},
            {"name": "🌳 Botanical Garden", "desc": "Serene green walkways, cycling tracks & flora", "url": "https://www.google.com/maps/search/?api=1&query=Botanical+Garden+Kondapur+Hyderabad"}
        ]
    },
    "Gachibowli": {
        "lat": 17.4401, "lon": 78.3489,
        "coords": "17.4401,78.3489",
        "intel": [
            "Hyderabad's premier sports and tech hub with 24/7 dining avenues.",
            "High concentration of rooftop football turfs and bowling alleys.",
            "Buzzing nightlife with craft breweries and fine dining lounges."
        ],
        "spotlights": [
            {"name": "🏏 HotFut Turf & Cafe", "desc": "Rooftop box cricket & football facility", "url": "https://www.google.com/maps/search/?api=1&query=HotFut+Gachibowli+Hyderabad"},
            {"name": "🎳 Smaaash Gaming Zone", "desc": "Arcade gaming, bowling alley & virtual reality", "url": "https://www.google.com/maps/search/?api=1&query=Smaaash+Gachibowli+Hyderabad"},
            {"name": "🍕 Olive Bistro & Bar", "desc": "Lakefront European dining near Durgam Cheruvu", "url": "https://www.google.com/maps/search/?api=1&query=Olive+Bistro+Durgam+Cheruvu+Hyderabad"}
        ]
    }
}

NEARBY_AREAS = {
    "Chandanagar": ["Miyapur", "Lingampally", "Kondapur"],
    "Miyapur": ["Chandanagar", "Lingampally", "Kondapur"],
    "Kondapur": ["Miyapur", "Gachibowli", "Lingampally"],
    "Gachibowli": ["Kondapur", "Financial District", "Miyapur"],
}

# ---------------------------------------------------------
# State Initialization
# ---------------------------------------------------------
if "location_mode_v2" not in st.session_state:
    st.session_state.location_mode_v2 = True
    st.session_state.location_enabled = True
    st.session_state.active_locality_name = "Location required"
    st.session_state.user_coords = ""
    st.session_state.custom_location_data = None
    st.session_state.live_location_resolved = False
    st.session_state.manual_location_selected = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_locality_name" not in st.session_state:
    st.session_state.active_locality_name = "Location required"
if "user_coords" not in st.session_state:
    st.session_state.user_coords = ""
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "last_graph_state" not in st.session_state:
    st.session_state.last_graph_state = None
if "show_map_chooser" not in st.session_state:
    st.session_state.show_map_chooser = False
if "custom_location_data" not in st.session_state:
    st.session_state.custom_location_data = None

# Request browser location once; recommendations remain unavailable until it resolves.
if st.session_state.location_enabled and not st.session_state.custom_location_data and not st.session_state.get("live_location_resolved", False) and not st.session_state.get("manual_location_selected", False):
    browser_location = location_component(key="location_request")
    if browser_location and browser_location.get("latitude") is not None and browser_location.get("longitude") is not None:
        live_lat = float(browser_location["latitude"])
        live_lon = float(browser_location["longitude"])
        live_lat, live_lon, live_label, live_data = resolve_coordinates(live_lat, live_lon)
        st.session_state.user_coords = f"{live_lat},{live_lon}"
        st.session_state.active_locality_name = live_label
        st.session_state.custom_location_data = live_data
        st.session_state.live_location_resolved = True
        st.rerun()
    elif browser_location and browser_location.get("error"):
        st.session_state.location_enabled = False
        st.session_state.active_locality_name = "Location unavailable"
        st.session_state.location_error = browser_location.get("message", "Browser location permission was denied.")
        st.rerun()

current_loc = st.session_state.active_locality_name
current_loc_data = st.session_state.custom_location_data or LOCALITY_DATA.get(
    current_loc,
    {"lat": None, "lon": None, "intel": [], "spotlights": []},
)
active_cat = st.session_state.selected_category
location_source = (
    "Live browser location"
    if st.session_state.get("live_location_resolved")
    else "Waiting for browser permission"
    if st.session_state.location_enabled
    else "Location off"
)

# ---------------------------------------------------------
# Unified Real-Time Live Weather Provider
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def get_live_radar_weather(lat: float, lon: float):
    return fetch_weather(lat, lon)

live_weather = (
    get_live_radar_weather(current_loc_data["lat"], current_loc_data["lon"])
    if current_loc_data["lat"] is not None and current_loc_data["lon"] is not None
    else {
        "temperature": "--",
        "condition": "Location off",
        "humidity": "--",
        "verdict": "Turn on the Active Hub location toggle to request your live location.",
    }
)

# ---------------------------------------------------------
# Dynamic Palette & Sizing (1.5x -> 2x -> 1x)
# ---------------------------------------------------------
if active_cat is None:
    eat_bg = "linear-gradient(145deg, #fff7ed, #ffedd5)"
    eat_border = "2px solid #fed7aa"
    eat_shadow = "0 8px 20px rgba(249, 115, 22, 0.18)"
    eat_color = "#ea580c"

    play_bg = "linear-gradient(145deg, #ecfdf5, #d1fae5)"
    play_border = "2px solid #a7f3d0"
    play_shadow = "0 8px 20px rgba(16, 185, 129, 0.18)"
    play_color = "#059669"

    relax_bg = "linear-gradient(145deg, #f5f3ff, #ede9fe)"
    relax_border = "2px solid #ddd6fe"
    relax_shadow = "0 8px 20px rgba(139, 92, 246, 0.18)"
    relax_color = "#7c3aed"
else:
    eat_bg = "linear-gradient(145deg, #fff7ed, #fed7aa)" if active_cat == "eat" else "rgba(255, 255, 255, 0.65)"
    eat_border = "3px solid #f97316" if active_cat == "eat" else "1px solid #e2e8f0"
    eat_shadow = "0 16px 36px rgba(249, 115, 22, 0.35)" if active_cat == "eat" else "0 4px 10px rgba(0,0,0,0.03)"
    eat_color = "#c2410c" if active_cat == "eat" else "#94a3b8"

    play_bg = "linear-gradient(145deg, #ecfdf5, #a7f3d0)" if active_cat == "play" else "rgba(255, 255, 255, 0.65)"
    play_border = "3px solid #10b981" if active_cat == "play" else "1px solid #e2e8f0"
    play_shadow = "0 16px 36px rgba(16, 185, 129, 0.35)" if active_cat == "play" else "0 4px 10px rgba(0,0,0,0.03)"
    play_color = "#047857" if active_cat == "play" else "#94a3b8"

    relax_bg = "linear-gradient(145deg, #f5f3ff, #ddd6fe)" if active_cat == "relax" else "rgba(255, 255, 255, 0.65)"
    relax_border = "3px solid #8b5cf6" if active_cat == "relax" else "1px solid #e2e8f0"
    relax_shadow = "0 16px 36px rgba(139, 92, 246, 0.35)" if active_cat == "relax" else "0 4px 10px rgba(0,0,0,0.03)"
    relax_color = "#6d28d9" if active_cat == "relax" else "#94a3b8"

eat_height = "125px" if active_cat is None else ("165px" if active_cat == "eat" else "75px")
play_height = "125px" if active_cat is None else ("165px" if active_cat == "play" else "75px")
relax_height = "125px" if active_cat is None else ("165px" if active_cat == "relax" else "75px")

eat_scale = "scale(1.0)" if active_cat is None else ("scale(1.04)" if active_cat == "eat" else "scale(0.92)")
play_scale = "scale(1.0)" if active_cat is None else ("scale(1.04)" if active_cat == "play" else "scale(0.92)")
relax_scale = "scale(1.0)" if active_cat is None else ("scale(1.04)" if active_cat == "relax" else "scale(0.92)")

eat_font = "1.55rem" if active_cat is None else ("2.1rem" if active_cat == "eat" else "1.1rem")
play_font = "1.55rem" if active_cat is None else ("2.1rem" if active_cat == "play" else "1.1rem")
relax_font = "1.55rem" if active_cat is None else ("2.1rem" if active_cat == "relax" else "1.1rem")

eat_opacity = "1.0" if active_cat in [None, "eat"] else "0.55"
play_opacity = "1.0" if active_cat in [None, "play"] else "0.55"
relax_opacity = "1.0" if active_cat in [None, "relax"] else "0.55"

st.markdown(f"""
<style>
.st-key-btn_cat_eat button {{
    height: {eat_height} !important;
    transform: {eat_scale} !important;
    border: {eat_border} !important;
    box-shadow: {eat_shadow} !important;
    background: {eat_bg} !important;
    opacity: {eat_opacity} !important;
}}
.st-key-btn_cat_eat button p {{
    font-size: {eat_font} !important;
    color: {eat_color} !important;
}}

.st-key-btn_cat_play button {{
    height: {play_height} !important;
    transform: {play_scale} !important;
    border: {play_border} !important;
    box-shadow: {play_shadow} !important;
    background: {play_bg} !important;
    opacity: {play_opacity} !important;
}}
.st-key-btn_cat_play button p {{
    font-size: {play_font} !important;
    color: {play_color} !important;
}}

.st-key-btn_cat_relax button {{
    height: {relax_height} !important;
    transform: {relax_scale} !important;
    border: {relax_border} !important;
    box-shadow: {relax_shadow} !important;
    background: {relax_bg} !important;
    opacity: {relax_opacity} !important;
}}
.st-key-btn_cat_relax button p {{
    font-size: {relax_font} !important;
    color: {relax_color} !important;
}}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Sub-Activity Options Matrix
# ---------------------------------------------------------
CATEGORY_OPTIONS = {
    "eat": [
        ["🍛 Biryani", "🍲 Indian & Mughlai", "🥞 South Indian Tiffins"],
        ["🌯 Shawarma", "🍜 Indo-Chinese", "🍕 Italian & Pizza"],
        ["🥘 Arabian Mandi", "🍢 Street Food & Chaat", "☕ Desserts & Irani Chai"]
    ],
    "play": [
        ["🏏 Box Cricket", "🎳 Bowling Alley", "🏎️ Go-Karting Track"],
        ["🏸 Badminton Court", "🎱 Snooker & Pool", "🏓 Pickleball Court"],
        ["⚽ Football Turf", "🎮 Gaming Lounge", "🏓 Table Tennis Club"]
    ],
    "relax": [
        ["🎬 Movie & Cinema", "🌅 Lakes & Promenade", "📚 Book Cafe & Library"],
        ["☕ Aesthetic Cafe", "💆 Spa & Wellness", "🌇 Sunset Viewpoint"],
        ["🌳 Botanical Gardens", "🛍️ Shopping Mall", "🏛️ Art & Heritage Walk"]
    ]
}

# ---------------------------------------------------------
# Agent Invoker
# ---------------------------------------------------------
def run_agent(query: str, existing_venues: list = None):
    if not st.session_state.user_coords:
        st.warning("Choose a location or turn on the Active Hub switch before discovering venues.")
        return
    with st.spinner("Scouting verified hyper-local venues..."):
        coords = st.session_state.user_coords or ""
        prev_state = st.session_state.last_graph_state or {}

        initial_state = {
            "user_query": query,
            "location_input": coords,
            "locality": st.session_state.active_locality_name,
            "lat": current_loc_data["lat"],
            "lon": current_loc_data["lon"],
            "category": prev_state.get("category", ""),
            "sub_activity": prev_state.get("sub_activity", ""),
            "weather_data": live_weather,
            "candidate_venues": existing_venues or [],
            "all_places_link": "",
            "retry_count": 0,
            "validation_status": "pending",
            "critic_notes": "",
            "final_response": "",
            "error": None
        }

        try:
            final_output = planmate_graph.invoke(initial_state)
            st.session_state.last_graph_state = final_output
            output_text = final_output.get("final_response", "Unable to generate plan.")
            st.session_state.messages.append({"role": "assistant", "content": output_text})
        except Exception as e:
            err_msg = f"❌ Execution error: {str(e)}"
            st.error(err_msg)
            st.session_state.messages.append({"role": "assistant", "content": err_msg})

# ---------------------------------------------------------
# 3-COLUMN RESPONSIVE LAYOUT
# ---------------------------------------------------------
left_side, center_main, right_side = st.columns([1, 2.5, 1], gap="medium")

# =========================================================
# LEFT COLUMN: LIVE WEATHER RADAR & DYNAMIC INTEL
# =========================================================
with left_side:
    st.markdown(f"""
    <div class="side-card">
        <div class="side-title">🌦️ {current_loc} Live Radar</div>
        <div style="font-size: 2.2rem; font-weight: 900; color: #0369a1; margin: 0.3rem 0;">{live_weather.get('temperature', '29.0°C')}</div>
        <div style="font-weight: 700; color: #334155; font-size: 0.95rem;">{live_weather.get('condition', 'Clear')} • Open-Meteo Synced</div>
        <div style="margin: 0.7rem 0; display: flex; gap: 6px; flex-wrap: wrap;">
            <span style="background: #e0f2fe; color: #0284c7; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;">💧 {live_weather.get('humidity', '55%')} Humidity</span>
            <span style="background: #dcfce7; color: #15803d; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 0.78rem;">🍃 Good AQI</span>
        </div>
        <div style="font-size: 0.85rem; color: #475569; margin-top: 0.5rem; line-height: 1.4;">
            {live_weather.get('verdict', 'Great conditions to step out today!')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    intel_items = current_loc_data.get("intel", [])
    intel_content = "<br>".join(f"• {item}" for item in intel_items) or "Turn on location to load nearby local intelligence."
    st.markdown(f"""
    <div class="side-card">
        <div class="side-title">⚡ {current_loc} Intel</div>
        <div style="font-size: 0.88rem; line-height: 1.55; color: #334155;">{intel_content}</div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# CENTER COLUMN: CORE HERO EXPERIENCE
# =========================================================
with center_main:
    st.markdown("""
    <div class="brand-header">
        <div class="brand-badge">⚡ Autonomous Discovery Agent</div>
        <div class="brand-title">PlanMate AI</div>
        <div class="brand-subtitle">Hyper-Local Day Planner • Verified Meteorological Grounding</div>
    </div>
    """, unsafe_allow_html=True)

    toggle_col, location_col = st.columns([0.12, 0.88], vertical_alignment="center")
    with toggle_col:
        toggle_label = "ON" if st.session_state.location_enabled else "OFF"
        toggle_key = "location_toggle_on" if st.session_state.location_enabled else "location_toggle_off"
        if st.button(toggle_label, key=toggle_key, help="Toggle live location on or off"):
            st.session_state.location_enabled = not st.session_state.location_enabled
            if st.session_state.location_enabled:
                st.session_state.active_locality_name = "Location required"
                st.session_state.user_coords = ""
                st.session_state.custom_location_data = None
                st.session_state.live_location_resolved = False
                st.session_state.manual_location_selected = False
            else:
                st.session_state.active_locality_name = "Location off"
                st.session_state.user_coords = ""
                st.session_state.custom_location_data = None
                st.session_state.live_location_resolved = False
            st.session_state.messages = []
            st.session_state.last_graph_state = None
            st.rerun()
    with location_col:
        st.markdown(f"""
        <div class="location-panel">
            <div class="loc-status-pill">
                <span>📍 Active Hub: <strong>{current_loc}</strong></span>
            </div>
            <div style="font-size: 0.85rem; color: #475569; font-weight: 700;">
                🛡️ Strict 6 km Radius Active • {location_source}
            </div>
        </div>
        """, unsafe_allow_html=True)

    nearby_areas = current_loc_data.get("nearby_areas", []) or NEARBY_AREAS.get(current_loc, [])
    area_columns = st.columns(4, vertical_alignment="center")
    for area_column, nearby_area in zip(area_columns[:3], nearby_areas[:3]):
        with area_column:
            if st.button(f"📍 {nearby_area}", key=f"nearby_area_{nearby_area.lower().replace(' ', '_')}", use_container_width=True):
                resolved = resolve_map_location(f"{nearby_area}, Hyderabad")
                if resolved:
                    lat, lon, label, custom_data = resolved
                    st.session_state.user_coords = f"{lat},{lon}"
                    st.session_state.active_locality_name = label
                    st.session_state.custom_location_data = custom_data
                    st.session_state.manual_location_selected = True
                    st.session_state.live_location_resolved = False
                    st.session_state.messages = []
                    st.session_state.last_graph_state = None
                    st.rerun()
    with area_columns[3]:
        if st.button("🗺️ Choose a different location", key="loc_choose_maps", use_container_width=True):
            st.session_state.show_map_chooser = not st.session_state.show_map_chooser
            st.rerun()

    if st.session_state.show_map_chooser:
        maps_query = urllib.parse.quote_plus(f"places to explore in {current_loc} Hyderabad")
        st.markdown('<div class="map-chooser-panel">', unsafe_allow_html=True)
        st.markdown("**Choose a location from Google Maps**", unsafe_allow_html=True)
        st.caption("Open Maps, select a place, copy its URL, paste it below, then apply it to PlanMate.")
        st.link_button("🌐 Open Google Maps", f"https://www.google.com/maps/search/?api=1&query={maps_query}")
        location_input = st.text_input(
            "Paste a Google Maps link, address, or coordinates",
            key="map_location_input",
            placeholder="https://maps.google.com/... or Kondapur, Hyderabad",
        )
        if st.button("Apply selected location", key="apply_map_location", type="primary"):
            resolved = resolve_map_location(location_input)
            if resolved:
                lat, lon, label, custom_data = resolved
                st.session_state.user_coords = f"{lat},{lon}"
                st.session_state.active_locality_name = label
                st.session_state.custom_location_data = custom_data
                st.session_state.manual_location_selected = True
                st.session_state.show_map_chooser = False
                st.session_state.messages = []
                st.session_state.last_graph_state = None
                st.rerun()
            else:
                st.error("Could not resolve that location. Paste a Google Maps URL or a Hyderabad address.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 1.2rem;'></div>", unsafe_allow_html=True)

    # Core 3 Category Tiles (Strictly EAT, PLAY, RELAX)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🍽️ EAT", key="btn_cat_eat", use_container_width=True):
            st.session_state.selected_category = None if active_cat == "eat" else "eat"
            st.rerun()

    with c2:
        if st.button("🏏 PLAY", key="btn_cat_play", use_container_width=True):
            st.session_state.selected_category = None if active_cat == "play" else "play"
            st.rerun()

    with c3:
        if st.button("🧘 RELAX", key="btn_cat_relax", use_container_width=True):
            st.session_state.selected_category = None if active_cat == "relax" else "relax"
            st.rerun()

    # Sub-Options Grid & Random Action
    if active_cat is not None:
        st.markdown("<div style='margin-top: 1.6rem;'></div>", unsafe_allow_html=True)
        active_matrix = CATEGORY_OPTIONS[active_cat]
        col_l, col_m, col_r = st.columns(3)
        all_active_options = []

        for row_idx in range(3):
            raw_l = active_matrix[0][row_idx]
            all_active_options.append(raw_l)
            with col_l:
                if st.button(raw_l, key=f"sub_{active_cat}_0_{row_idx}", use_container_width=True):
                    clean_term = raw_l.split(" ", 1)[-1]
                    prompt = f"I want to eat {clean_term} in {current_loc}" if active_cat == "eat" else f"I want to do {clean_term} in {current_loc}"
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    run_agent(prompt)
                    st.rerun()

            raw_m = active_matrix[1][row_idx]
            all_active_options.append(raw_m)
            with col_m:
                if st.button(raw_m, key=f"sub_{active_cat}_1_{row_idx}", use_container_width=True):
                    clean_term = raw_m.split(" ", 1)[-1]
                    prompt = f"I want to eat {clean_term} in {current_loc}" if active_cat == "eat" else f"I want to do {clean_term} in {current_loc}"
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    run_agent(prompt)
                    st.rerun()

            raw_r = active_matrix[2][row_idx]
            all_active_options.append(raw_r)
            with col_r:
                if st.button(raw_r, key=f"sub_{active_cat}_2_{row_idx}", use_container_width=True):
                    clean_term = raw_r.split(" ", 1)[-1]
                    prompt = f"I want to eat {clean_term} in {current_loc}" if active_cat == "eat" else f"I want to do {clean_term} in {current_loc}"
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    run_agent(prompt)
                    st.rerun()

        st.markdown("<div style='margin-top: 1.1rem;'></div>", unsafe_allow_html=True)
        if st.button(f"🎲 Pick Random {active_cat.upper()} in {current_loc}", key=f"rnd_{active_cat}", use_container_width=True):
            chosen_pick = random.choice(all_active_options)
            clean_term = chosen_pick.split(" ", 1)[-1]
            prompt = f"Pick something for me: I want {clean_term} in {current_loc}"
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_agent(prompt)
            st.rerun()

    # Mood Filter Row
    st.markdown("<div style='margin-top: 1.5rem; margin-bottom: 0.3rem;'></div>", unsafe_allow_html=True)
    st.caption("✨ Quick Mood Filters")
    v1, v2, v3, v4 = st.columns(4)
    with v1:
        if st.button("🌙 Open Late", key="vibe_night", use_container_width=True):
            prompt = f"Find places open late night in {current_loc}"
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_agent(prompt)
            st.rerun()
    with v2:
        if st.button("👥 Group Hangout", key="vibe_group", use_container_width=True):
            prompt = f"Find best spots for a group hangout with friends in {current_loc}"
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_agent(prompt)
            st.rerun()
    with v3:
        if st.button("💰 Budget Friendly", key="vibe_budget", use_container_width=True):
            prompt = f"Find budget-friendly places under ₹500 in {current_loc}"
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_agent(prompt)
            st.rerun()
    with v4:
        if st.button("☕ Quiet & Chill", key="vibe_quiet", use_container_width=True):
            prompt = f"Find quiet, peaceful aesthetic spots in {current_loc}"
            st.session_state.messages.append({"role": "user", "content": prompt})
            run_agent(prompt)
            st.rerun()

    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)

    # Chat Feed (3 Verified Spots + 4th Map Card)
    for idx, msg in enumerate(st.session_state.messages):
        avatar_choice = USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR
        with st.chat_message(msg["role"], avatar=avatar_choice):
            st.markdown(msg["content"], unsafe_allow_html=True)

            if msg["role"] == "assistant" and idx == len(st.session_state.messages) - 1:
                if st.session_state.last_graph_state and st.session_state.last_graph_state.get("sub_activity"):
                    activity = st.session_state.last_graph_state["sub_activity"]
                    if st.button(f"➕ Discover More {activity.title()} Spots", key=f"more_btn_{idx}"):
                        curr_venues = st.session_state.last_graph_state.get("candidate_venues", [])
                        run_agent(f"Show 3 more places for {activity}", existing_venues=curr_venues)
                        st.rerun()

    user_prompt = st.chat_input("E.g., I want to eat biryani, play box cricket, or find a quiet cafe...")
    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(user_prompt)
        run_agent(user_prompt)
        st.rerun()

# =========================================================
# RIGHT COLUMN: DYNAMIC SPOTLIGHT
# =========================================================
with right_side:
    spotlight_items = []
    for sp in current_loc_data["spotlights"]:
        badge = (
            f'<div class="trend-badge">'
            f'<div style="font-weight: 800; font-size: 0.9rem; color: #0f172a;">{sp["name"]}</div>'
            f'<div style="font-size: 0.8rem; color: #475569; margin-bottom: 4px;">{sp["desc"]}</div>'
            f'<a href="{sp["url"]}" target="_blank" style="font-size: 0.78rem; font-weight: 700; color: #2563eb; text-decoration: none;">View on Maps →</a>'
            f'</div>'
        )
        spotlight_items.append(badge)

    badges_html = "".join(spotlight_items)

    st.markdown(
        f'<div class="side-card">'
        f'<div class="side-title">🔥 {current_loc} Spotlight</div>'
        f'{badges_html}'
        f'</div>'
        f'<div class="side-card">'
        f'<div class="side-title">🛡️ Guardrail Rules</div>'
        f'<div style="font-size: 0.82rem; color: #64748b; line-height: 1.55;">'
        f'✅ Top 3 Grounded Venues<br>'
        f'✅ 4th Option: Live User Maps Picker<br>'
        f'✅ Synced {current_loc} Perimeter<br>'
        f'❌ Zero Fictional Venues'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )
