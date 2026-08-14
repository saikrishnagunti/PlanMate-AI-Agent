import os
import time
import math
import urllib.parse
from pathlib import Path
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

# =========================================================================
# 1. Environment & API Setup
# =========================================================================
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ GEMINI_API_KEY is missing from your .env file! Add GEMINI_API_KEY=your_key in .env")

# =========================================================================
# 2. Distance Calculation (Haversine Formula)
# =========================================================================
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geographical distance in kilometers between two GPS points."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

# =========================================================================
# 3. Comprehensive Sub-Activity Keyword Normalizer
# =========================================================================
def clean_search_term(category: str, sub: str) -> str:
    """Translates user intents across Play, Eat, and Relax into high-match OSM keywords."""
    sub_lower = sub.lower().strip()
    
    mapping = {
        # --- PLAY & SPORTS ---
        "boxcricket": "box cricket turf",
        "box cricket": "box cricket turf",
        "cricket": "cricket ground turf",
        "cricket ground": "cricket ground",
        "cricket turf": "cricket turf",
        "football": "football ground turf",
        "futsal": "futsal turf arena",
        "soccer": "football turf",
        "badminton": "badminton court academy",
        "badminton court": "badminton academy",
        "tennis": "tennis court club",
        "lawn tennis": "tennis court",
        "table tennis": "table tennis academy",
        "tt": "table tennis",
        "squash": "squash court",
        "pickleball": "pickleball court",
        "padel": "padel tennis court",
        "basketball": "basketball court",
        "volleyball": "volleyball court",
        "gokart": "go karting circuit track",
        "go kart": "go kart track",
        "gokarting": "go karting circuit",
        "go karting": "go karting circuit",
        "ekart": "karting circuit",
        "karting": "go karting track",
        "bowling": "bowling alley",
        "bowling alley": "bowling alley",
        "snooker": "snooker pool parlor",
        "pool": "snooker pool club",
        "billiards": "billiards parlor",
        "arcade": "gaming arcade zone",
        "gaming zone": "gaming arcade",
        "laser tag": "laser tag arena",
        "paintball": "paintball arena",
        "vr games": "vr gaming arcade",
        "escape room": "escape room game",
        "gym": "gym fitness center",
        "swimming": "swimming pool",
        "swimming pool": "swimming pool",
        "trampoline": "trampoline park",
        "skating": "skating rink roller",

        # --- EAT & DINING ---
        "dinner": "restaurant",
        "dinner restaurant": "restaurant",
        "lunch": "restaurant",
        "breakfast": "tiffin breakfast restaurant",
        "brunch": "cafe restaurant",
        "supper": "restaurant",
        "midnight food": "midnight dhaba restaurant",
        "buffet": "buffet restaurant",
        "fine dine": "fine dining restaurant",
        "family restaurant": "family restaurant",
        "dhaba": "dhaba restaurant",
        "rooftop": "rooftop restaurant lounge",
        "biryani": "biryani restaurant",
        "hyderabadi biryani": "biryani restaurant",
        "mandi": "mandi restaurant",
        "mandhi": "mandi restaurant",
        "south indian": "south indian restaurant tiffin",
        "north indian": "north indian restaurant",
        "thali": "thali restaurant",
        "andhra meals": "andhra restaurant",
        "punjabi": "punjabi dhaba restaurant",
        "dosa": "tiffin dosa center",
        "street food": "street food court",
        "italian": "italian pizza pasta restaurant",
        "pizza": "pizzeria pizza restaurant",
        "burger": "burger restaurant cafe",
        "chinese": "chinese restaurant noodles",
        "pan asian": "pan asian restaurant",
        "momos": "momo restaurant cafe",
        "ramen": "ramen noodle bar",
        "japanese": "japanese sushi restaurant",
        "sushi": "sushi bar restaurant",
        "korean": "korean restaurant",
        "shawarma": "shawarma grill restaurant",
        "kebabs": "kebab grill restaurant",
        "cafe": "cafe coffee shop",
        "coffee": "cafe espresso coffee shop",
        "chai": "tea chai cafe",
        "tea": "tea chai cafe",
        "bakery": "bakery cake shop",
        "ice cream": "ice cream parlor",
        "dessert": "dessert ice cream parlor",
        "pub": "pub brewery bar",
        "brewery": "microbrewery pub",

        # --- RELAX & ENTERTAINMENT ---
        "movie": "cinema movie theatre multiplex",
        "cinema": "cinema multiplex",
        "theatre": "theatre multiplex",
        "imax": "imax cinema multiplex",
        "spa": "spa massage wellness center",
        "massage": "thai massage spa",
        "ayurvedic spa": "ayurvedic wellness spa",
        "salon": "beauty salon parlor",
        "read a book": "library",
        "book": "library book store",
        "library": "public library reading hall",
        "study hall": "reading hall study space",
        "bookstore": "book shop bookstore",
        "park": "public park garden",
        "garden": "botanical garden park",
        "lake": "lake waterfront park",
        "museum": "museum gallery",
        "shopping": "shopping mall shopping center",
        "mall": "shopping mall multiplex",
        "resort": "day out resort club"
    }

    if sub_lower in mapping:
        return mapping[sub_lower]
    
    for k, v in mapping.items():
        if k in sub_lower:
            return v
            
    return sub_lower

# =========================================================================
# 4. Live API Tool 1: Real-Time Weather (wttr.in)
# =========================================================================
def get_live_weather(city: str) -> dict:
    """Fetches real-time weather and precipitation status for any city/locality."""
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

# =========================================================================
# 5. Live API Tool 2: Dynamic Venue & Distance Search (OpenStreetMap)
# =========================================================================
def search_places_with_maps(location: str, category: str, sub_activity: str) -> list:
    """Queries real live places/venues, calculates real distance, and creates Maps links."""
    headers = {"User-Agent": "PlanMate-LiveAgent/3.0 (dev-student@vectorclan.ai)"}
    
    # 1. Resolve Origin Coordinates
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

    # 2. Normalize search term
    clean_keyword = clean_search_term(category, sub_activity)

    # 3. Query OpenStreetMap
    query_1 = f"{clean_keyword}, {location}, Hyderabad"
    search_url_1 = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query_1)}&format=json&limit=4"
    
    results = []
    try:
        data = requests.get(search_url_1, headers=headers, timeout=10).json()
        
        # Bounding box fallback if first try has 0 results
        if not data and origin_lat and origin_lon:
            viewbox = f"{origin_lon - 0.09},{origin_lat + 0.09},{origin_lon + 0.09},{origin_lat - 0.09}"
            search_url_2 = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(clean_keyword)}&viewbox={viewbox}&bounded=1&format=json&limit=4"
            data = requests.get(search_url_2, headers=headers, timeout=10).json()

        for place in data:
            dest_lat = float(place["lat"])
            dest_lon = float(place["lon"])
            
            dist = f"~{calculate_distance(origin_lat, origin_lon, dest_lat, dest_lon)} km away" if origin_lat else "Nearby"
            name = place.get("display_name", "").split(",")[0]
            area = ", ".join(place.get("display_name", "").split(",")[1:3]).strip()
            
            # Real destination coordinates link
            gmaps_url = f"https://www.google.com/maps/search/?api=1&query={dest_lat},{dest_lon}"
            
            results.append({
                "name": name,
                "area": area if area else location,
                "distance": dist,
                "google_maps_link": gmaps_url
            })
    except Exception as e:
        print(f"Search Warning: {e}")

    # Fallback to direct Maps search if no tagged node exists
    if not results:
        maps_query = urllib.parse.quote_plus(f"{clean_keyword} near {location} Hyderabad")
        results.append({
            "name": f"Top rated {sub_activity.title()} spots in {location}",
            "area": location,
            "distance": "Within your vicinity",
            "google_maps_link": f"https://www.google.com/maps/search/?api=1&query={maps_query}"
        })

    return results

# =========================================================================
# 6. Function Tool Schemas for Gemini
# =========================================================================
weather_tool_schema = types.FunctionDeclaration(
    name="get_live_weather",
    description="Gets real-time weather and precipitation status for a given city or locality.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "city": types.Schema(type="STRING", description="Target city or area name (e.g. Miyapur, Gachibowli, Hyderabad)")
        },
        required=["city"]
    )
)

places_tool_schema = types.FunctionDeclaration(
    name="search_places_with_maps",
    description="Searches for physical venues, sports arenas, food spots, cinemas, or spas with distances and direct Google Maps links.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "location": types.Schema(type="STRING", description="User's city or neighborhood (e.g. Madhapur, Shamshabad)"),
            "category": types.Schema(type="STRING", description="Primary category: 'play', 'eat', or 'relax'"),
            "sub_activity": types.Schema(type="STRING", description="Specific activity (e.g. cricket, biryani, movie, gokart, library, spa)")
        },
        required=["location", "category", "sub_activity"]
    )
)

agent_tools = types.Tool(function_declarations=[weather_tool_schema, places_tool_schema])

# =========================================================================
# 7. System Instructions & Guardrails
# =========================================================================
SYSTEM_INSTRUCTION = """
You are 'PlanMate', an intelligent daily activity and lifestyle planning agent.

OPERATIONAL RULES:
1. Always call `get_live_weather` for the user's location.
2. Always call `search_places_with_maps` to fetch real venues with distances and map links.
3. If an outdoor activity (cricket, tennis, gokart) is requested and it is raining, explicitly warn the user and recommend indoor alternatives (indoor turf, bowling, cinema).
4. Format output with clean bullet points: Venue Name, Distance (~X km), and a clickable link: `[Open in Google Maps](URL)`.

STRICT GUARDRAILS:
- Answer ONLY requests related to daily planning (activities, dining, sports, movies, books/libraries, spas, weather).
- For unrelated requests (e.g., coding help, homework, academic math, politics), politely decline:
  "I am PlanMate, your personal day planner! Please choose an activity (Play, Eat, Relax) so I can help plan your day."
"""

# =========================================================================
# 8. Safe Execution Helper with Rate-Limit Backoff
# =========================================================================
def send_message_with_retry(chat, payload, max_retries=3):
    """Retries request automatically if a 429 RESOURCE_EXHAUSTED error occurs."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(payload)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait_sec = 20 * (attempt + 1)
                print(f"\n⏳ Rate limit cooldown. Pausing for {wait_sec}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                raise e
    raise RuntimeError("Rate limit persisted. Please wait a minute and try again.")

# =========================================================================
# 9. Main Interactive Loop
# =========================================================================
def run_planmate():
    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[agent_tools],
            temperature=0.4
        )
    )

    print("=" * 65)
    print("🎯 PlanMate (Weather + Dynamic OSM Venues + Google Maps) Ready!")
    print("Categories: Play | Eat | Relax")
    print("Type 'exit' to quit.")
    print("=" * 65 + "\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("\n🤖 PlanMate: Have a wonderful day! Goodbye.")
            break
        if not user_input:
            continue

        try:
            response = send_message_with_retry(chat, user_input)

            # ReAct Loop: Resolve any tool calls requested by the model
            while response.function_calls:
                for fn in response.function_calls:
                    fn_name = fn.name
                    args = fn.args
                    print(f"⚙️ [TOOL CALL] Executing: {fn_name}({args})")

                    if fn_name == "get_live_weather":
                        tool_result = get_live_weather(args.get("city", "Hyderabad"))
                    elif fn_name == "search_places_with_maps":
                        tool_result = search_places_with_maps(
                            args.get("location", "Hyderabad"),
                            args.get("category", "play"),
                            args.get("sub_activity", "activity")
                        )
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' not implemented"}

                    # Feed tool response back to the conversation
                    response = send_message_with_retry(
                        chat,
                        types.Part.from_function_response(
                            name=fn_name,
                            response={"result": tool_result}
                        )
                    )

            print(f"\nPlanMate:\n{response.text}\n")
            print("-" * 65)

        except Exception as e:
            print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    run_planmate()