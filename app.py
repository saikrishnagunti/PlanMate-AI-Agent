import os
import re
import time
import urllib.parse
from pathlib import Path
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

# -------------------------------------------------------------------------
# 1. Environment & API Setup
# -------------------------------------------------------------------------
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

st.set_page_config(page_title="PlanMate AI", page_icon="🎯", layout="centered")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    try:
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

if not api_key:
    st.error("❌ Missing GEMINI_API_KEY. Please verify your local .env file contains: GEMINI_API_KEY=your_key")
    st.stop()

# -------------------------------------------------------------------------
# 2. Complete ~80-Entry Keyword Normalizer
# -------------------------------------------------------------------------
def clean_search_term(category: str, sub: str) -> str:
    """Translates user intents across Play, Eat, and Relax into high-match search keywords."""
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
        "pickle ball": "sports centre",
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
        "sandwich": "sandwich cafe fast food",
        "frankie": "frankie roll wrap",
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

# -------------------------------------------------------------------------
# 3. Live Grounding Tools (Weather & Generic Search Links)
# -------------------------------------------------------------------------
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

def search_places_with_maps(location: str, category: str, sub_activity: str) -> list:
    """Generates verified Google Maps category search queries without distance math."""
    clean_keyword = clean_search_term(category, sub_activity)
    maps_query = urllib.parse.quote_plus(f"{clean_keyword} near {location} Hyderabad")
    
    return [
        {
            "name": f"Top rated {sub_activity.title()} spots in {location}",
            "area": location,
            "google_maps_link": f"https://www.google.com/maps/search/?api=1&query={maps_query}"
        }
    ]

# -------------------------------------------------------------------------
# 4. Tool Declarations & System Instructions
# -------------------------------------------------------------------------
weather_tool = types.FunctionDeclaration(
    name="get_live_weather",
    description="Gets real-time weather and precipitation status for a given city or locality.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"city": types.Schema(type="STRING", description="Target city or area name (e.g. Manikonda, Madhapur, Kondapur)")},
        required=["city"]
    )
)

places_tool = types.FunctionDeclaration(
    name="search_places_with_maps",
    description="Searches for physical venues, sports arenas, food spots, cinemas, or spas with direct Google Maps links.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "location": types.Schema(type="STRING", description="User's city or neighborhood"),
            "category": types.Schema(type="STRING", description="Primary category: 'play', 'eat', or 'relax'"),
            "sub_activity": types.Schema(type="STRING", description="Specific activity (e.g. badminton, frankie, sushi, gokarting)")
        },
        required=["location", "category", "sub_activity"]
    )
)

agent_tools = types.Tool(function_declarations=[weather_tool, places_tool])

SYSTEM_INSTRUCTION = """
You are 'PlanMate', an autonomous, real-time daily activity and lifestyle planning agent.

CORE IDENTITY & PURPOSE:
- Help users organize their leisure time across: 'Play' (sports/recreation), 'Eat' (dining/cafes), and 'Relax' (libraries/spas/movies).
- Ground recommendations in real-world data using external tools; never invent or hallucinate venue names or weather.

CRITICAL OPERATIONAL RULES:

1. ANTI-HALLUCINATION & STRICT GROUNDING:
   - You MUST ONLY recommend the EXACT category label returned in the `search_places_with_maps` tool response (e.g., "Top rated Frankie spots in Kondapur").
   - NEVER invent or fabricate specific business, restaurant, shop, or venue names (e.g., do NOT invent names like 'Smaaash', 'Kathi Junction', 'Roll Corner', 'Aish', or 'Zobha').
   - Output the category directly with its Google Maps search link.

2. PARALLEL TOOL DISPATCH:
   - On every activity inquiry, execute BOTH `get_live_weather` AND `search_places_with_maps` concurrently.

3. LOCALITY PERSISTENCE:
   - Always remember the user's active locality (e.g., Kondapur, Manikonda, Madhapur) across follow-up queries.
   - Never switch cities or assume foreign locations unless explicitly commanded.

4. MANDATORY MULTI-LINE MARKDOWN FORMATTING:
   - NEVER write bullet points horizontally on a single line.
   - You MUST follow the EXACT layout below with newlines and sub-bullets:

⛅ **Weather Update**
- **Temperature:** [Temp in °C]
- **Condition:** [Condition string]
- **Humidity:** [Humidity %]
- **Verdict:** [1-2 sentences on outdoor/indoor suitability]

---

📍 **Recommended Options**
- **[Venue Name or Category as returned by tool]**
  * **Details:** [1 sentence factual overview of what to enjoy]
  * **Directions:** [Open in Google Maps](URL)

TOPICAL GUARDRAILS:
- Answer ONLY requests related to daily planning (activities, dining, sports, movies, relaxation).
- For off-topic requests (coding, homework, politics), politely reply:
  "I am PlanMate, your personal day planner! Please choose an activity (Play, Eat, Relax) so I can help plan your day."
"""

# -------------------------------------------------------------------------
# 5. Streamlit Chat Engine with Dynamic Rate-Limit Cooldown
# -------------------------------------------------------------------------
def send_message_with_retry_ui(chat, payload, max_retries=4):
    """Safely sends messages with dynamic rate-limit detection and a live countdown timer."""
    for attempt in range(max_retries):
        try:
            return chat.send_message(payload)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay_match = re.search(r"retry in ([\d\.]+)s", err_str)
                field_match = re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", err_str)
                
                if delay_match:
                    wait_sec = float(delay_match.group(1)) + 1.0
                elif field_match:
                    wait_sec = float(field_match.group(1)) + 1.0
                else:
                    wait_sec = 25.0 * (attempt + 1)
                
                status_placeholder = st.empty()
                remaining = int(wait_sec)
                while remaining > 0:
                    status_placeholder.warning(f"⏳ Free-tier rate limit reached. Cooling down: resuming in {remaining}s...")
                    time.sleep(1)
                    remaining -= 1
                status_placeholder.empty()
            else:
                raise e
    raise RuntimeError("Rate limit persisted past maximum retries. Please wait 1 minute and try again.")

st.title("🎯 PlanMate AI")
st.caption("Autonomous Day Planner • Live Weather Grounding • Google Maps Navigation")

# 1. Message History
if "messages" not in st.session_state:
    st.session_state.messages = []

# 2. Persistent Client
if "client" not in st.session_state:
    st.session_state.client = genai.Client(api_key=api_key)

# 3. Persistent Chat Session
if "chat" not in st.session_state:
    st.session_state.chat = st.session_state.client.chats.create(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[agent_tools],
            temperature=0.2
        )
    )

# Render past conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_prompt = st.chat_input("E.g., I am in Kondapur now and I want to play gokarting...")

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Checking live weather & finding venues..."):
            try:
                response = send_message_with_retry_ui(st.session_state.chat, user_prompt)
                
                # ReAct Multi-turn Tool Loop
                while response.function_calls:
                    for fn in response.function_calls:
                        if fn.name == "get_live_weather":
                            tool_res = get_live_weather(fn.args.get("city", "Kondapur"))
                        elif fn.name == "search_places_with_maps":
                            tool_res = search_places_with_maps(
                                fn.args.get("location", "Kondapur"),
                                fn.args.get("category", "play"),
                                fn.args.get("sub_activity", "activity")
                            )
                        else:
                            tool_res = {"error": "Unknown tool"}

                        response = send_message_with_retry_ui(
                            st.session_state.chat,
                            types.Part.from_function_response(
                                name=fn.name,
                                response={"result": tool_res}
                            )
                        )

                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})

            except Exception as ex:
                st.error(f"Execution Error: {ex}")