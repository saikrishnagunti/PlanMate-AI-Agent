import os
import math
import urllib.parse
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load local .env file
env_path = Path(__file__).parent / ".env"
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if not api_key:
    st.error("❌ Missing GEMINI_API_KEY. Please verify your local .env file contains: GEMINI_API_KEY=your_key")
    st.stop()

# -------------------------------------------------------------------------
# Distance & Tool Functions
# -------------------------------------------------------------------------
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def get_live_weather(city: str) -> dict:
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            curr = data["current_condition"][0]
            desc = curr["weatherDesc"][0]["value"].lower()
            is_rainy = any(w in desc for w in ["rain", "drizzle", "shower", "storm", "thunder"])
            return {
                "city": city,
                "temperature": f"{curr['temp_C']}°C",
                "condition": curr["weatherDesc"][0]["value"],
                "humidity": f"{curr['humidity']}%",
                "outdoor_suitable": not is_rainy
            }
        return {"error": "Could not fetch weather data"}
    except Exception as e:
        return {"error": str(e)}

def search_places_with_maps(location: str, category: str, sub_activity: str) -> list:
    headers = {"User-Agent": "PlanMate-WebAgent/3.0"}
    search_context = f"{location}, Hyderabad, India" if "hyderabad" not in location.lower() else location
    geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(search_context)}&format=json&limit=1"
    
    origin_lat, origin_lon = None, None
    try:
        geo_res = requests.get(geo_url, headers=headers, timeout=10).json()
        if geo_res:
            origin_lat = float(geo_res[0]["lat"])
            origin_lon = float(geo_res[0]["lon"])
    except Exception:
        pass

    query_1 = f"{sub_activity}, {location}, Hyderabad"
    search_url_1 = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query_1)}&format=json&limit=4"
    results = []
    
    try:
        data = requests.get(search_url_1, headers=headers, timeout=10).json()
        if not data and origin_lat and origin_lon:
            viewbox = f"{origin_lon - 0.09},{origin_lat + 0.09},{origin_lon + 0.09},{origin_lat - 0.09}"
            search_url_2 = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(sub_activity)}&viewbox={viewbox}&bounded=1&format=json&limit=4"
            data = requests.get(search_url_2, headers=headers, timeout=10).json()

        for place in data:
            dest_lat = float(place["lat"])
            dest_lon = float(place["lon"])
            dist = f"~{calculate_distance(origin_lat, origin_lon, dest_lat, dest_lon)} km away" if origin_lat else "Nearby"
            name = place.get("display_name", "").split(",")[0]
            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={dest_lat},{dest_lon}"
            results.append({
                "name": name,
                "distance": dist,
                "google_maps_link": gmaps_url
            })
    except Exception:
        pass

    if not results:
        maps_query = urllib.parse.quote_plus(f"{sub_activity} near {location} Hyderabad")
        results.append({
            "name": f"Verified {sub_activity.title()} spots in {location}",
            "distance": "In this area",
            "google_maps_link": f"https://www.google.com/maps/search/?api=1&query={maps_query}"
        })
    return results

# -------------------------------------------------------------------------
# Schemas & Agent Setup
# -------------------------------------------------------------------------
weather_tool = types.FunctionDeclaration(
    name="get_live_weather",
    description="Gets live weather and precipitation for a city/area.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"city": types.Schema(type="STRING", description="City or area name")},
        required=["city"]
    )
)

places_tool = types.FunctionDeclaration(
    name="search_places_with_maps",
    description="Searches for physical venues with real distances and Google Maps links.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "location": types.Schema(type="STRING", description="City or neighborhood"),
            "category": types.Schema(type="STRING", description="Primary category: play, eat, or relax"),
            "sub_activity": types.Schema(type="STRING", description="Activity name like cricket, spa, biryani, movie")
        },
        required=["location", "category", "sub_activity"]
    )
)

agent_tools = types.Tool(function_declarations=[weather_tool, places_tool])

SYSTEM_INSTRUCTION = """
You are 'PlanMate', an autonomous lifestyle and activity planner.
1. Always call `get_live_weather` for the user's location.
2. Always call `search_places_with_maps` to get real venues and map links.
3. If weather is bad/rainy, warn the user and recommend indoor alternatives.
4. Format output with bullet points and markdown links: [Open in Google Maps](URL).
STRICT GUARDRAIL: Only answer leisure, sports, food, and daily plan requests. Decline coding, homework, or academic math.
"""

# -------------------------------------------------------------------------
# UI Interface
# -------------------------------------------------------------------------
st.title("🎯 PlanMate AI")
st.caption("Autonomous Day Planner • Live Weather • Google Maps Navigation")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_prompt = st.chat_input("E.g., I am in Miyapur and want to read a book...")

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        client = genai.Client(api_key=api_key)
        chat = client.chats.create(
            model="gemini-3.6-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[agent_tools],
                temperature=0.4
            )
        )

        with st.spinner("Checking live weather & finding venues..."):
            response = chat.send_message(user_prompt)
            while response.function_calls:
                for fn in response.function_calls:
                    if fn.name == "get_live_weather":
                        res = get_live_weather(fn.args.get("city", "Hyderabad"))
                    elif fn.name == "search_places_with_maps":
                        res = search_places_with_maps(
                            fn.args.get("location", "Hyderabad"),
                            fn.args.get("category", "play"),
                            fn.args.get("sub_activity", "activity")
                        )
                    else:
                        res = {"error": "Tool not found"}

                    response = chat.send_message(
                        types.Part.from_function_response(
                            name=fn.name,
                            response={"result": res}
                        )
                    )

            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})