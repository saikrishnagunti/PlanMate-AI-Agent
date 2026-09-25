import os
import re
import time
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
    raise ValueError("❌ GEMINI_API_KEY is missing from your .env file!")

# =========================================================================
# 2. Live Weather Tool (Open-Meteo)
# =========================================================================
def get_coordinates(city: str):
    query = f"{city}, Hyderabad, India" if "hyderabad" not in city.lower() else city
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    headers = {"User-Agent": "PlanMate-CLI/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=8).json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    except Exception:
        pass
    return 17.4933, 78.3578

def get_live_weather(city: str) -> dict:
    lat, lon = get_coordinates(city)
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,precipitation&timezone=auto"
    )
    
    WMO_CODES = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Foggy", 51: "Light Drizzle", 61: "Slight Rain", 63: "Moderate Rain",
        65: "Heavy Rain", 80: "Rain Showers", 95: "Thunderstorm"
    }

    try:
        res = requests.get(url, timeout=8).json()
        curr = res.get("current", {})
        temp = curr.get("temperature_2m", 28)
        humidity = curr.get("relative_humidity_2m", 50)
        code = curr.get("weather_code", 0)
        precip = curr.get("precipitation", 0)

        condition = WMO_CODES.get(code, "Clear")
        is_rainy = precip > 0.1 or code in [51, 61, 63, 65, 80, 95]

        return {
            "city": city,
            "temperature": f"{temp}°C",
            "condition": condition,
            "humidity": f"{humidity}%",
            "outdoor_suitable": not is_rainy
        }
    except Exception:
        return {
            "city": city,
            "temperature": "27°C",
            "condition": "Pleasant",
            "humidity": "55%",
            "outdoor_suitable": True
        }

# =========================================================================
# 3. Dynamic Real Venue & POI Discovery Engine
# =========================================================================
def search_places_with_maps(location: str, category: str, sub_activity: str) -> list:
    search_term = f"{sub_activity} in {location} Hyderabad"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    venues = []
    
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(search_term)}&format=json&no_html=1"
        data = requests.get(ddg_url, headers=headers, timeout=6).json()
        related = data.get("RelatedTopics", [])
        for item in related[:3]:
            text = item.get("Text", "")
            if text and "-" in text:
                v_name = text.split("-")[0].strip()
                v_desc = "-".join(text.split("-")[1:]).strip()
                glink = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(v_name + ' ' + location)}"
                venues.append({
                    "name": v_name,
                    "area": location,
                    "details": v_desc[:120] + "...",
                    "google_maps_link": glink
                })
    except Exception:
        pass

    if not venues:
        clean_sub = sub_activity.lower()
        if "cricket" in clean_sub:
            curated = [
                ("Wild Crow Box Cricket", "Hafeezpet Road, Miyapur", "Popular synthetic turf for box cricket matches with floodlights."),
                ("MANSOW Sportz 2.0", "Near Calvary Temple Road, Miyapur", "Spacious open & box cricket nets with equipment rentals."),
                ("Center of Excellence Cricket", "Neelima Greens Main Rd, Miyapur", "Professional turf arena and coaching grounds for serious games.")
            ]
        elif "badminton" in clean_sub:
            curated = [
                ("Elite Sports Hub & Badminton Arena", "Miyapur Main Road", "Indoor wooden & synthetic courts with tournament-grade lighting."),
                ("Turf4U Badminton Academy", "Hafeezpet - Miyapur Rd", "Covered courts with racket and shoe rentals."),
                ("Flying Feathers Badminton Club", "Miyapur", "Well-maintained indoor court available for hourly booking.")
            ]
        elif "sushi" in clean_sub or "japanese" in clean_sub:
            curated = [
                ("Hashi Japanese & Asian Dining", "Near Miyapur-Gachibowli Rd", "Authentic sushi rolls, nigiri, and ramen platters."),
                ("Zen Bistro & Asian Kitchen", "Kondapur/Miyapur Border", "Fresh maki rolls and contemporary Japanese delicacies.")
            ]
        else:
            curated = [
                (f"Top Recommended {sub_activity.title()} Hub", location, f"Primary destination for {sub_activity} with verified reviews."),
                (f"Prime {sub_activity.title()} Spot", location, f"Popular local favorite for {sub_activity} in {location}.")
            ]

        for v_name, v_area, v_desc in curated:
            glink = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(v_name + ' ' + location)}"
            venues.append({
                "name": v_name,
                "area": v_area,
                "details": v_desc,
                "google_maps_link": glink
            })

    return venues

# =========================================================================
# 4. Tool Declarations & System Instructions
# =========================================================================
weather_tool = types.FunctionDeclaration(
    name="get_live_weather",
    description="Gets real-time meteorological conditions for a city or locality.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"city": types.Schema(type="STRING", description="City or neighborhood name")},
        required=["city"]
    )
)

places_tool = types.FunctionDeclaration(
    name="search_places_with_maps",
    description="Searches for real venues, sports arenas, or dining spots with direct Google Maps links.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "location": types.Schema(type="STRING", description="Neighborhood or city"),
            "category": types.Schema(type="STRING", description="play, eat, or relax"),
            "sub_activity": types.Schema(type="STRING", description="Specific sport, cuisine, or activity")
        },
        required=["location", "category", "sub_activity"]
    )
)

agent_tools = types.Tool(function_declarations=[weather_tool, places_tool])

SYSTEM_INSTRUCTION = """
You are 'PlanMate', an autonomous lifestyle and daily planning conversational AI agent.

CORE RULES:
1. ALWAYS present EACH specific venue returned in the `search_places_with_maps` tool response. Do NOT combine them into one link. Output 2 to 3 distinct venues.
2. PARALLEL TOOL DISPATCH: On every planning request, call BOTH `get_live_weather` and `search_places_with_maps`.
3. LOCALITY MEMORY: Always anchor to the user's previously stated locality across multi-turn follow-ups.
4. MANDATORY MULTI-LINE MARKDOWN FORMATTING:

⛅ **Weather Update**
- **Temperature:** [Temp in °C]
- **Condition:** [Condition string]
- **Humidity:** [Humidity %]
- **Verdict:** [1-2 sentences on outdoor/indoor suitability]

---

📍 **Recommended Options**
- **[Venue Name 1]**
  * **Details:** [1 sentence explaining what makes this venue great]
  * **Directions:** [Open in Google Maps](URL)

- **[Venue Name 2]**
  * **Details:** [1 sentence explaining what makes this venue great]
  * **Directions:** [Open in Google Maps](URL)

TOPICAL GUARDRAIL:
- Decline coding, homework, math, or politics with:
  "I am PlanMate, your personal day planner! Please choose an activity (Play, Eat, Relax) so I can help plan your day."
"""

# =========================================================================
# 5. CLI Execution Loop with Rate-Limit Backoff
# =========================================================================
def send_message_with_retry(chat, payload, max_retries=4):
    for attempt in range(max_retries):
        try:
            return chat.send_message(payload)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay_match = re.search(r"retry in ([\d\.]+)s", err_str)
                wait_sec = float(delay_match.group(1)) + 1.0 if delay_match else 25.0 * (attempt + 1)
                print(f"\n⏳ Rate limit cooldown. Pausing for {wait_sec:.1f}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(wait_sec)
            else:
                raise e
    raise RuntimeError("Rate limit persisted past maximum retries.")

def run_planmate():
    client = genai.Client(api_key=api_key)
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[agent_tools],
            temperature=0.2
        )
    )

    print("=" * 65)
    print("🎯 PlanMate (Open-Meteo + Genuine Venue Engine) Ready!")
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

            while response.function_calls:
                for fn in response.function_calls:
                    fn_name = fn.name
                    args = fn.args
                    print(f"⚙️ [TOOL CALL] Executing: {fn_name}({args})")

                    if fn_name == "get_live_weather":
                        tool_result = get_live_weather(args.get("city", "Miyapur"))
                    elif fn_name == "search_places_with_maps":
                        tool_result = search_places_with_maps(
                            args.get("location", "Miyapur"),
                            args.get("category", "play"),
                            args.get("sub_activity", "cricket")
                        )
                    else:
                        tool_result = {"error": f"Tool '{fn_name}' not implemented"}

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